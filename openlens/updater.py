"""GitHub Releases update checks and standalone-build installation.

The application ships three ways: a PyInstaller executable/bundle, a source
checkout, and a pip install. Only the frozen build can replace itself. Everyone
else is sent to the release page, because silently dropping a new binary beside
a pip-managed package would be worse than asking the user to download it.

Nothing here imports Qt. The startup dialog owns the thread and the widgets;
this module owns the network request, version comparison, asset selection, and
the small helper script that replaces a running executable once it exits.
"""

import hashlib
import json
import logging
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Tuple

from . import __version__

logger = logging.getLogger(__name__)

#: GitHub's latest-release endpoint, which excludes drafts and prereleases.
RELEASES_API_URL = "https://api.github.com/repos/pmaasz/openLens/releases/latest"

#: Human-facing release page, used for pip/dev installs and missing assets.
RELEASES_PAGE_URL = "https://github.com/pmaasz/openLens/releases/latest"

STATUS_UPDATE_AVAILABLE = "update_available"
STATUS_UP_TO_DATE = "up_to_date"
STATUS_NO_ASSET = "no_asset"
STATUS_ERROR = "error"

#: How much of an asset response is read at a time.
_DOWNLOAD_CHUNK = 256 * 1024

#: Prefix of the temporary directory :meth:`UpdateChecker.download` creates
#: when the caller does not supply a destination. The helper scripts use it to
#: decide whether they own (and may remove) the directory.
_UPDATE_TEMP_PREFIX = "openlens-update-"

#: Magic bytes that identify a downloadable executable or archive. A payload
#: that does not start with one of these is not an installer (for example an
#: HTML error page) and must never be executed.
_EXECUTABLE_MAGICS = (
    b"\x7fELF",  # ELF (Linux)
    b"MZ",  # PE (Windows)
    b"PK\x03\x04",  # ZIP (macOS bundle)
    b"\xcf\xfa\xed\xfe",  # Mach-O 64-bit
    b"\xca\xfe\xba\xbe",  # Mach-O universal / Java class
    b"\xfe\xed\xfa\xce",  # Mach-O 32-bit (big endian)
    b"\xfe\xed\xfa\xcf",  # Mach-O 64-bit (big endian)
)

#: A release digest is published as ``sha256:<hex>`` (GitHub's ``digest``
#: field) or as a bare hex string.
_DIGEST_RE = re.compile(r"^(?:sha256:)?([0-9a-fA-F]{64})$")

#: Network operations get a bound so a dead connection cannot leave the
#: startup check spinning forever. The work happens on a worker thread.
_DEFAULT_TIMEOUT = 8.0


def cleanup_download(downloaded: os.PathLike) -> None:
    """Remove a downloaded update and the temporary directory that held it.

    :meth:`UpdateChecker.download` creates an ``openlens-update-*`` directory
    when no destination is supplied. The GUI failure path and the installer
    helper call this to remove the payload, the helper script and the directory
    together. A caller-supplied destination directory is left in place; only
    the payload is removed.

    Args:
        downloaded: A path returned by :meth:`UpdateChecker.download`.
    """
    path = Path(downloaded)
    if path.parent.name.startswith(_UPDATE_TEMP_PREFIX):
        shutil.rmtree(path.parent, ignore_errors=True)
    else:
        path.unlink(missing_ok=True)


_VERSION_RE = re.compile(
    r"^(?:openlens[-_ ]?)?v?"
    r"(?P<major>\d+)(?:\.(?P<minor>\d+))?(?:\.(?P<patch>\d+))?"
    r"(?:-(?P<pre>[0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ReleaseAsset:
    """One downloadable file attached to a GitHub release."""

    name: str
    url: str
    size: int = 0
    digest: str = ""
    sha256: str = ""
    checksum: str = ""

    def __post_init__(self) -> None:
        # Accept any of the common spellings so callers (and the GitHub API,
        # which uses ``digest``) all populate the same field.
        chosen = self.digest or self.sha256 or self.checksum
        if chosen and chosen != self.digest:
            object.__setattr__(self, "digest", chosen)


@dataclass(frozen=True)
class UpdateCheckResult:
    """Outcome of comparing the running version with the latest release.

    ``status`` is one of the module-level ``STATUS_*`` constants. ``asset`` is
    only set when ``status`` is ``STATUS_UPDATE_AVAILABLE``; ``release_url`` is
    always populated so the UI has a fallback.
    """

    status: str
    current_version: str
    latest_version: Optional[str] = None
    release_url: str = RELEASES_PAGE_URL
    asset: Optional[ReleaseAsset] = None
    message: str = ""


@dataclass(frozen=True)
class InstallPlan:
    """What the UI should do with a downloaded update.

    ``kind`` is ``"replace"`` (run ``script`` after this process exits),
    ``"open_bundle"`` (open a freshly extracted macOS app), or
    ``"release_page"`` (no self-update is possible). ``target`` is the
    executable replaced by a ``"replace"`` plan, ``app_path`` is the extracted
    macOS bundle, and ``release_url`` is the page to open for a
    ``"release_page"`` plan.
    """

    kind: str
    target: Optional[Path] = None
    script: Optional[Path] = None
    app_path: Optional[Path] = None
    release_url: Optional[str] = None


def _normalise_system(system: Optional[str] = None) -> str:
    """Return a canonical ``windows``/``linux``/``darwin`` platform name."""
    value = (system or platform.system()).strip().lower()
    if value.startswith("win"):
        return "windows"
    if value in {"darwin", "macos", "mac"}:
        return "darwin"
    if value.startswith("linux"):
        return "linux"
    return value


def _normalise_machine(machine: Optional[str] = None) -> str:
    """Return a lower-case machine architecture."""
    return (machine or platform.machine()).strip().lower()


def version_key(version: str) -> Tuple[int, int, int, int, str]:
    """Turn a release tag or version into a sortable key.

    Accepts ``0.7.0``, ``v0.7.0``, and the release-please form
    ``openlens-v0.7.0``. A final release sorts above a prerelease with the same
    numeric components.

    Args:
        version: Version text or tag.

    Returns:
        ``(major, minor, patch, release_rank, prerelease)``.

    Raises:
        ValueError: If *version* does not look like a version number.
    """
    match = _VERSION_RE.match(version.strip())
    if match is None:
        raise ValueError(f"Not a version: {version!r}")

    prerelease = (match.group("pre") or "").lower()
    return (
        int(match.group("major")),
        int(match.group("minor") or 0),
        int(match.group("patch") or 0),
        1 if not prerelease else 0,
        prerelease,
    )


def is_newer(candidate: str, current: str) -> bool:
    """Return whether *candidate* is a newer release than *current*."""
    return version_key(candidate) > version_key(current)


def version_text(version: str) -> str:
    """Return the display form (``major.minor.patch``) of a version or tag."""
    match = _VERSION_RE.match(version.strip())
    if match is None:
        raise ValueError(f"Not a version: {version!r}")
    return "{}.{}.{}".format(
        int(match.group("major")),
        int(match.group("minor") or 0),
        int(match.group("patch") or 0),
    )


def asset_for_platform(
    assets: Iterable[dict], system: Optional[str] = None, machine: Optional[str] = None
) -> Optional[ReleaseAsset]:
    """Pick the release asset built for this platform and architecture.

    The release workflow publishes exactly one Windows x64 executable, one
    Linux x64 executable, and two macOS zip bundles. Unsupported architectures
    get ``None`` rather than a binary that will not run.

    Args:
        assets: Release ``assets`` entries from the GitHub API.
        system: Platform name; defaults to :func:`platform.system`.
        machine: Architecture; defaults to :func:`platform.machine`.

    Returns:
        The matching asset, or ``None``.
    """
    platform_name = _normalise_system(system)
    architecture = _normalise_machine(machine)

    if platform_name == "windows":
        if architecture not in {"x86_64", "amd64"}:
            return None
        suffix = "-Windows.exe"
    elif platform_name == "linux":
        if architecture not in {"x86_64", "amd64"}:
            return None
        suffix = "-Linux"
    elif platform_name == "darwin":
        if architecture in {"arm64", "aarch64"}:
            suffix = "-macOS-arm64.zip"
        elif architecture in {"x86_64", "amd64", "i386", "i686"}:
            suffix = "-macOS-x64.zip"
        else:
            return None
    else:
        return None

    for asset in assets:
        name = asset.get("name")
        url = asset.get("browser_download_url")
        if not isinstance(name, str) or not isinstance(url, str):
            continue
        if name.endswith(suffix):
            size = asset.get("size", 0)
            digest = asset.get("digest") or asset.get("sha256") or asset.get("checksum") or ""
            if not isinstance(digest, str):
                digest = ""
            return ReleaseAsset(
                name=name,
                url=url,
                size=size if isinstance(size, int) and size > 0 else 0,
                digest=digest,
            )
    return None


def _default_opener(request: urllib.request.Request, timeout: float):
    """Open a request with the standard library."""
    return urllib.request.urlopen(request, timeout=timeout)


class UpdateChecker:
    """Query GitHub Releases, compare versions, and download the matching asset."""

    def __init__(
        self,
        current_version: Optional[str] = None,
        system: Optional[str] = None,
        machine: Optional[str] = None,
        opener: Optional[Callable[[urllib.request.Request, float], Any]] = None,
        api_url: str = RELEASES_API_URL,
        releases_page: str = RELEASES_PAGE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the checker.

        Args:
            current_version: Running version; defaults to ``openlens.__version__``.
            system: Platform name override, for tests.
            machine: Architecture override, for tests.
            opener: ``urlopen``-compatible callable, for tests.
            api_url: Latest-release API endpoint.
            releases_page: Fallback release page.
            timeout: Per-request timeout in seconds.
        """
        self.current_version = current_version or __version__
        self.system = system
        self.machine = machine
        self.api_url = api_url
        self.releases_page = releases_page
        self.timeout = timeout
        self._opener = opener or _default_opener

    def _open(self, url: str, accept: str) -> Any:
        """Open *url* with OpenLens identification headers."""
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": f"OpenLens/{self.current_version}",
                "Accept": accept,
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        return self._opener(request, self.timeout)

    def check(self) -> UpdateCheckResult:
        """Check the latest release without raising on network/API failures.

        Returns:
            An :class:`UpdateCheckResult`. Failures become
            ``STATUS_ERROR`` with a user-presentable message.
        """
        try:
            response = self._open(self.api_url, "application/vnd.github+json")
            try:
                payload = json.loads(response.read())
            finally:
                response.close()
        except Exception as exc:  # noqa: BLE001 - startup must never crash
            logger.warning("Update check failed: %s", exc)
            return UpdateCheckResult(
                status=STATUS_ERROR,
                current_version=self.current_version,
                release_url=self.releases_page,
                message=str(exc),
            )

        if not isinstance(payload, dict) or not isinstance(payload.get("tag_name"), str):
            logger.warning("Update response did not contain a release tag")
            return UpdateCheckResult(
                status=STATUS_ERROR,
                current_version=self.current_version,
                release_url=self.releases_page,
                message="The latest release did not include a tag_name.",
            )

        tag = payload["tag_name"]
        try:
            latest = version_text(tag)
            newer = is_newer(tag, self.current_version)
        except ValueError as exc:
            logger.warning("Could not compare release tag %r: %s", tag, exc)
            return UpdateCheckResult(
                status=STATUS_ERROR,
                current_version=self.current_version,
                release_url=self.releases_page,
                message=str(exc),
            )

        release_url = payload.get("html_url")
        if not isinstance(release_url, str) or not release_url:
            release_url = self.releases_page

        if not newer:
            return UpdateCheckResult(
                status=STATUS_UP_TO_DATE,
                current_version=self.current_version,
                latest_version=latest,
                release_url=release_url,
            )

        assets = payload.get("assets", [])
        if not isinstance(assets, list):
            assets = []
        asset = asset_for_platform(assets, self.system, self.machine)
        if asset is None:
            return UpdateCheckResult(
                status=STATUS_NO_ASSET,
                current_version=self.current_version,
                latest_version=latest,
                release_url=release_url,
            )

        return UpdateCheckResult(
            status=STATUS_UPDATE_AVAILABLE,
            current_version=self.current_version,
            latest_version=latest,
            release_url=release_url,
            asset=asset,
        )

    def download(
        self, result: UpdateCheckResult, destination: Optional[os.PathLike] = None
    ) -> Path:
        """Download the asset described by *result*.

        The download is written beside the final name and only moved into place
        after a complete, correctly sized body. A failed download leaves no
        half-written executable behind.

        Args:
            result: A result with a non-``None`` asset.
            destination: Directory to download into; a new temporary directory
                is used when omitted. The caller owns that directory and can
                remove it with :func:`cleanup_download` once the update has
                been installed or abandoned.

        Returns:
            The downloaded file.

        Raises:
            ValueError: If there is no asset or the received size is wrong.
            OSError: If the connection fails while reading.
        """
        asset = result.asset
        if asset is None:
            raise ValueError("No release asset to download")
        if not asset.size or asset.size <= 0:
            raise ValueError(
                f"Release asset {asset.name!r} has no known size; refusing to download"
            )

        created_temp_dir = destination is None
        target_dir = (
            Path(destination)
            if destination is not None
            else Path(tempfile.mkdtemp(prefix=_UPDATE_TEMP_PREFIX))
        )
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            filename = Path(asset.name).name
            if not filename or filename in {".", ".."}:
                filename = Path(asset.url.split("?", 1)[0]).name
            if not filename or filename in {".", ".."}:
                raise ValueError(f"Release asset has no usable filename: {asset.name!r}")
            target = target_dir / filename
            partial = target.with_name(target.name + ".part")

            response = self._open(asset.url, "application/octet-stream")
            try:
                with partial.open("wb") as handle:
                    while True:
                        chunk = response.read(_DOWNLOAD_CHUNK)
                        if not chunk:
                            break
                        handle.write(chunk)
            except Exception:
                partial.unlink(missing_ok=True)
                raise
            finally:
                response.close()

            received = partial.stat().st_size
            if received != asset.size:
                partial.unlink(missing_ok=True)
                raise ValueError(
                    f"Downloaded {received} bytes for {asset.name}, expected {asset.size}"
                )

            body = partial.read_bytes()

            # Verify the published digest when one is available.
            digest_match = _DIGEST_RE.match(asset.digest.strip()) if asset.digest else None
            if asset.digest and digest_match is None:
                partial.unlink(missing_ok=True)
                raise ValueError(
                    f"Release asset {asset.name!r} has an invalid digest: {asset.digest!r}"
                )
            if digest_match is not None:
                expected = digest_match.group(1).lower()
                actual = hashlib.sha256(body).hexdigest()
                if actual != expected:
                    partial.unlink(missing_ok=True)
                    raise ValueError(
                        f"Digest mismatch for {asset.name}: expected {expected}, got {actual}"
                    )

            # Sanity-check that the payload is an executable/archive and not, for
            # example, an HTML error page.
            if not any(body.startswith(magic) for magic in _EXECUTABLE_MAGICS):
                partial.unlink(missing_ok=True)
                raise ValueError(
                    f"Downloaded payload for {asset.name} is not a recognised executable "
                    f"(first bytes: {body[:8]!r})"
                )

            try:
                partial.replace(target)
            except Exception:
                partial.unlink(missing_ok=True)
                raise
            return target
        except Exception:
            if created_temp_dir:
                shutil.rmtree(target_dir, ignore_errors=True)
            raise


def is_frozen() -> bool:
    """Return whether the running application is a PyInstaller build."""
    return bool(getattr(sys, "frozen", False) or getattr(sys, "_MEIPASS", None))


def _linux_update_script(
    downloaded: Path,
    target: Path,
    pid: int,
    log: Path,
    cleanup_dir: Optional[Path] = None,
) -> str:
    """Build the shell script that swaps a Linux executable after exit."""
    new_file = target.with_name(target.name + ".new")
    backup_file = target.with_name(target.name + ".old")
    cleanup = (
        f"rmdir -- {shlex.quote(str(cleanup_dir))} 2>/dev/null || true\n"
        if cleanup_dir is not None
        else ""
    )
    return """#!/bin/sh
# OpenLens updater: wait for the running copy to exit, then replace it.
set -u
pid={pid}
while kill -0 "$pid" 2>/dev/null; do
    sleep 0.2
done
# Keep the previous binary so a failed update can be rolled back.
cp -p -- {target} {backup_file} 2>/dev/null || true
if cp -- {downloaded} {new_file} && chmod +x {new_file} && mv -f -- {new_file} {target}; then
    nohup {target} >/dev/null 2>&1 &
else
    rm -f -- {new_file}
    printf '%s\\n' "Could not replace {target}" > {log}
    nohup {target} >/dev/null 2>&1 &
fi
rm -f -- {downloaded}
rm -f -- "$0"
{cleanup}""".format(
        pid=pid,
        downloaded=shlex.quote(str(downloaded)),
        new_file=shlex.quote(str(new_file)),
        target=shlex.quote(str(target)),
        backup_file=shlex.quote(str(backup_file)),
        log=shlex.quote(str(log)),
        cleanup=cleanup,
    )


def _windows_update_script(
    downloaded: Path,
    target: Path,
    pid: int,
    log: Path,
    cleanup_dir: Optional[Path] = None,
) -> str:
    """Build the batch script that swaps a Windows executable after exit."""
    cleanup = (
        f'rmdir /S /Q "{cleanup_dir}" >NUL 2>&1\n' if cleanup_dir is not None else 'del "%~f0"\n'
    )
    return """@echo off
setlocal
:wait
tasklist /FI "PID eq {pid}" 2>NUL | find "{pid}" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak >NUL
    goto wait
)
copy /Y "{target}" "{target}.old" >NUL
copy /Y "{downloaded}" "{target}" >NUL
if errorlevel 1 (
    echo Could not replace "{target}" > "{log}"
    start "" "{target}"
) else (
    start "" "{target}"
)
del /Q "{downloaded}" >NUL 2>&1
del "%~f0"
{cleanup}""".format(
        pid=pid,
        downloaded=downloaded,
        target=target,
        log=log,
        cleanup=cleanup,
    )


def _safe_extract(archive: Path, destination: Path) -> None:
    """Extract a macOS app zip without allowing paths outside *destination*.

    ``ditto`` is preferred on macOS because it preserves the symlinks and
    extended attributes inside a signed ``.app``. Python's :mod:`zipfile` is
    only a fallback for other platforms and test environments.
    """
    root = destination.resolve()
    with zipfile.ZipFile(archive) as bundle:
        for member in bundle.infolist():
            resolved = (destination / member.filename).resolve()
            if resolved != root and root not in resolved.parents:
                raise ValueError(f"Unsafe path in update archive: {member.filename}")

    ditto = shutil.which("ditto") if sys.platform == "darwin" else None
    if ditto:
        subprocess.run(
            [ditto, "-x", "-k", str(archive), str(destination)],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return

    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(destination)


class UpdateInstaller:
    """Plan and launch installation for the current build type."""

    def __init__(
        self,
        frozen: Optional[bool] = None,
        system: Optional[str] = None,
        executable: Optional[os.PathLike] = None,
        pid: Optional[int] = None,
        downloads_dir: Optional[os.PathLike] = None,
    ) -> None:
        """Initialize the installer.

        Args:
            frozen: Whether this is a PyInstaller build; detected when omitted.
            system: Platform override, for tests.
            executable: Running executable path; defaults to ``sys.executable``.
            pid: Process ID to wait for; defaults to the current PID.
            downloads_dir: Where a macOS bundle is extracted; defaults to the
                user's Downloads directory.
        """
        self.frozen = is_frozen() if frozen is None else frozen
        self.system = _normalise_system(system)
        self.executable = Path(executable) if executable is not None else Path(sys.executable)
        self.pid = os.getpid() if pid is None else pid
        self.downloads_dir = (
            Path(downloads_dir) if downloads_dir is not None else Path.home() / "Downloads"
        )

    def can_self_update(self) -> bool:
        """Return whether this build can install a downloaded update itself."""
        return self.frozen and self.system in {"windows", "linux", "darwin"}

    def prepare(self, downloaded: os.PathLike, result: UpdateCheckResult) -> InstallPlan:
        """Turn a downloaded asset into an actionable installation plan.

        Args:
            downloaded: The file returned by :meth:`UpdateChecker.download`.
            result: The update result that produced it.

        Returns:
            An :class:`InstallPlan`.

        Raises:
            FileNotFoundError: If *downloaded* is missing.
            ValueError: If a macOS archive contains no application bundle.
        """
        path = Path(downloaded)
        if not path.is_file():
            raise FileNotFoundError(f"Downloaded update not found: {path}")

        if not self.can_self_update():
            return InstallPlan(kind="release_page", release_url=result.release_url)

        if self.system == "darwin":
            return self._prepare_macos(path)

        script_suffix = ".bat" if self.system == "windows" else ".sh"
        script = path.with_name(f"apply_openlens_update{script_suffix}")
        cleanup_dir = None
        log = path.with_name("openlens-update-error.log")
        if path.parent.name.startswith(_UPDATE_TEMP_PREFIX):
            cleanup_dir = path.parent
            # Keep the diagnostic outside the directory the helper removes.
            log = cleanup_dir.parent / "openlens-update-error.log"
        if self.system == "windows":
            script.write_text(
                _windows_update_script(
                    path.resolve(),
                    self.executable.resolve(),
                    self.pid,
                    log,
                    cleanup_dir,
                ),
                encoding="utf-8",
            )
        else:
            script.write_text(
                _linux_update_script(
                    path.resolve(),
                    self.executable.resolve(),
                    self.pid,
                    log,
                    cleanup_dir,
                ),
                encoding="utf-8",
            )
            script.chmod(0o700)
        return InstallPlan(kind="replace", target=self.executable, script=script)

    def _prepare_macos(self, archive: Path) -> InstallPlan:
        """Extract a macOS zip and locate its application bundle."""
        root = self.downloads_dir
        try:
            root.mkdir(parents=True, exist_ok=True)
        except OSError:
            root = archive.parent
        destination = root / archive.stem
        if destination.exists():
            destination = Path(tempfile.mkdtemp(prefix=f"{archive.stem}-", dir=str(root)))
        else:
            destination.mkdir(parents=True)
        _safe_extract(archive, destination)
        bundles = sorted(
            (entry for entry in destination.rglob("*.app") if entry.is_dir()),
            key=lambda entry: len(entry.parts),
        )
        if not bundles:
            raise ValueError("The macOS update archive did not contain an app bundle")
        if archive.parent.name.startswith(_UPDATE_TEMP_PREFIX):
            try:
                destination.resolve().relative_to(archive.parent.resolve())
            except ValueError:
                # The bundle was extracted outside the download directory, so
                # the archive (and its temporary directory) is no longer needed.
                shutil.rmtree(archive.parent, ignore_errors=True)
        return InstallPlan(kind="open_bundle", app_path=bundles[0])

    def launch(self, plan: InstallPlan) -> None:
        """Start the helper that applies *plan*, detached from this process.

        Args:
            plan: The plan returned by :meth:`prepare`.

        Raises:
            ValueError: For a ``"release_page"`` plan, which the UI opens.
        """
        if plan.kind == "open_bundle":
            if plan.app_path is None:
                raise ValueError("macOS install plan has no app path")
            subprocess.Popen(
                ["open", str(plan.app_path)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
            )
            return

        if plan.kind != "replace" or plan.script is None:
            raise ValueError("This update must be installed from the release page")

        if self.system == "windows":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            subprocess.Popen(
                ["cmd.exe", "/c", str(plan.script)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                ["/bin/sh", str(plan.script)],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
