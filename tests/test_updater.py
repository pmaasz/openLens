#!/usr/bin/env python3
"""Update-check and standalone update-installation tests (#42)."""

import io
import json
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from openlens.updater import (
    STATUS_ERROR,
    STATUS_NO_ASSET,
    STATUS_UP_TO_DATE,
    STATUS_UPDATE_AVAILABLE,
    InstallPlan,
    ReleaseAsset,
    UpdateCheckResult,
    UpdateChecker,
    UpdateInstaller,
    asset_for_platform,
    is_newer,
    version_key,
)

API_URL = "https://api.example.test/releases/latest"
RELEASE_URL = "https://example.test/releases/tag/openlens-v0.8.0"


class FakeOpener:
    """Return canned HTTP bytes for each requested URL."""

    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def __call__(self, request, timeout):
        url = request.full_url
        self.requests.append((request, timeout))
        value = self.responses[url]
        if isinstance(value, Exception):
            raise value
        if isinstance(value, bytes):
            return io.BytesIO(value)
        return value


class FailingRead(io.BytesIO):
    """A response whose body fails halfway through a download."""

    def read(self, size=-1):
        raise OSError("connection dropped")


def release_payload(tag="openlens-v0.8.0", assets=None):
    """Build a minimal GitHub release API response."""
    if assets is None:
        assets = [
            {
                "name": "OpenLens-0.8.0-Windows.exe",
                "browser_download_url": "https://example.test/OpenLens-Windows.exe",
                "size": 10,
            },
            {
                "name": "OpenLens-0.8.0-Linux",
                "browser_download_url": "https://example.test/OpenLens-Linux",
                "size": 7,
            },
            {
                "name": "OpenLens-0.8.0-macOS-arm64.zip",
                "browser_download_url": "https://example.test/OpenLens-arm64.zip",
                "size": 11,
            },
            {
                "name": "OpenLens-0.8.0-macOS-x64.zip",
                "browser_download_url": "https://example.test/OpenLens-x64.zip",
                "size": 12,
            },
            {
                "name": "openlens-0.8.0-py3-none-any.whl",
                "browser_download_url": "https://example.test/openlens.whl",
                "size": 13,
            },
        ]
    return json.dumps(
        {"tag_name": tag, "html_url": RELEASE_URL, "assets": assets}
    ).encode("utf-8")


def checker_for(payload, system="Linux", machine="x86_64", current="0.7.0"):
    opener = FakeOpener({API_URL: payload})
    return UpdateChecker(
        current_version=current,
        system=system,
        machine=machine,
        opener=opener,
        api_url=API_URL,
    )


class TestVersionComparison(unittest.TestCase):
    def test_release_prefixes_are_accepted(self):
        self.assertEqual(version_key("openlens-v0.8.0")[:3], (0, 8, 0))
        self.assertEqual(version_key("v1.2.3")[:3], (1, 2, 3))
        self.assertEqual(version_key("0.7")[:3], (0, 7, 0))

    def test_newer_patch_is_newer(self):
        self.assertTrue(is_newer("0.7.1", "0.7.0"))
        self.assertFalse(is_newer("0.7.0", "0.7.0"))
        self.assertFalse(is_newer("0.6.9", "0.7.0"))

    def test_release_beats_its_prerelease(self):
        self.assertTrue(is_newer("1.0.0", "1.0.0-beta.1"))
        self.assertFalse(is_newer("1.0.0-beta.1", "1.0.0"))

    def test_build_metadata_does_not_change_order(self):
        self.assertEqual(version_key("1.0.0+build.7"), version_key("1.0.0"))

    def test_garbage_version_is_rejected(self):
        with self.assertRaises(ValueError):
            version_key("not-a-version")


class TestAssetSelection(unittest.TestCase):
    def setUp(self):
        self.assets = json.loads(release_payload())["assets"]

    def test_windows_x64_gets_the_exe(self):
        asset = asset_for_platform(self.assets, system="Windows", machine="AMD64")
        self.assertEqual(asset.name, "OpenLens-0.8.0-Windows.exe")

    def test_linux_x64_gets_the_linux_binary(self):
        asset = asset_for_platform(self.assets, system="Linux", machine="x86_64")
        self.assertEqual(asset.name, "OpenLens-0.8.0-Linux")

    def test_macos_arm64_gets_the_arm_bundle(self):
        asset = asset_for_platform(self.assets, system="Darwin", machine="arm64")
        self.assertEqual(asset.name, "OpenLens-0.8.0-macOS-arm64.zip")

    def test_macos_intel_gets_the_x64_bundle(self):
        asset = asset_for_platform(self.assets, system="Darwin", machine="x86_64")
        self.assertEqual(asset.name, "OpenLens-0.8.0-macOS-x64.zip")

    def test_unsupported_architecture_has_no_asset(self):
        self.assertIsNone(
            asset_for_platform(self.assets, system="Linux", machine="aarch64")
        )
        self.assertIsNone(
            asset_for_platform(self.assets, system="Windows", machine="arm64")
        )

    def test_wheels_are_not_mistaken_for_platform_builds(self):
        assets = [
            {
                "name": "openlens-0.8.0-py3-none-any.whl",
                "browser_download_url": "https://example.test/openlens.whl",
                "size": 13,
            }
        ]
        self.assertIsNone(asset_for_platform(assets, system="Linux", machine="x86_64"))


class TestUpdateCheck(unittest.TestCase):
    def test_newer_release_with_asset_reports_update_available(self):
        result = checker_for(release_payload()).check()

        self.assertEqual(result.status, STATUS_UPDATE_AVAILABLE)
        self.assertEqual(result.current_version, "0.7.0")
        self.assertEqual(result.latest_version, "0.8.0")
        self.assertEqual(result.asset.name, "OpenLens-0.8.0-Linux")
        self.assertEqual(result.release_url, RELEASE_URL)

    def test_current_release_reports_up_to_date(self):
        result = checker_for(release_payload(tag="openlens-v0.7.0")).check()

        self.assertEqual(result.status, STATUS_UP_TO_DATE)
        self.assertIsNone(result.asset)

    def test_platform_without_asset_reports_no_asset(self):
        payload = release_payload(
            assets=[
                {
                    "name": "OpenLens-0.8.0-Windows.exe",
                    "browser_download_url": "https://example.test/OpenLens-Windows.exe",
                    "size": 10,
                }
            ]
        )
        result = checker_for(payload, system="Linux", machine="x86_64").check()

        self.assertEqual(result.status, STATUS_NO_ASSET)
        self.assertEqual(result.latest_version, "0.8.0")
        self.assertIsNone(result.asset)

    def test_network_error_is_reported_without_raising(self):
        opener = FakeOpener({API_URL: OSError("offline")})
        checker = UpdateChecker(
            current_version="0.7.0",
            system="Linux",
            machine="x86_64",
            opener=opener,
            api_url=API_URL,
        )

        result = checker.check()

        self.assertEqual(result.status, STATUS_ERROR)
        self.assertIn("offline", result.message)

    def test_malformed_release_is_reported_without_raising(self):
        result = checker_for(b'{"assets": []}').check()

        self.assertEqual(result.status, STATUS_ERROR)
        self.assertIn("tag", result.message.lower())

    def test_api_request_has_a_user_agent(self):
        opener = FakeOpener({API_URL: release_payload()})
        checker = UpdateChecker(
            current_version="0.7.0",
            system="Linux",
            machine="x86_64",
            opener=opener,
            api_url=API_URL,
        )

        checker.check()

        self.assertTrue(opener.requests)
        request, _timeout = opener.requests[0]
        self.assertIn("OpenLens", request.get_header("User-agent"))


class TestDownload(unittest.TestCase):
    def test_asset_is_written_and_size_checked(self):
        asset = ReleaseAsset(
            "OpenLens-0.8.0-Linux", "https://example.test/OpenLens-Linux", 7
        )
        opener = FakeOpener({asset.url: b"payload"})
        checker = UpdateChecker(opener=opener)
        result = UpdateCheckResult(
            status=STATUS_UPDATE_AVAILABLE,
            current_version="0.7.0",
            latest_version="0.8.0",
            asset=asset,
        )

        with tempfile.TemporaryDirectory() as temp:
            path = checker.download(result, destination=temp)

            self.assertEqual(path.read_bytes(), b"payload")
            self.assertEqual(path.name, "OpenLens-0.8.0-Linux")

    def test_size_mismatch_removes_the_partial_file(self):
        asset = ReleaseAsset(
            "OpenLens-0.8.0-Linux", "https://example.test/OpenLens-Linux", 99
        )
        opener = FakeOpener({asset.url: b"short"})
        checker = UpdateChecker(opener=opener)
        result = UpdateCheckResult(
            status=STATUS_UPDATE_AVAILABLE,
            current_version="0.7.0",
            latest_version="0.8.0",
            asset=asset,
        )

        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                checker.download(result, destination=temp)
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_read_failure_removes_the_partial_file(self):
        asset = ReleaseAsset(
            "OpenLens-0.8.0-Linux", "https://example.test/OpenLens-Linux", 7
        )
        opener = FakeOpener({asset.url: FailingRead(b"payload")})
        checker = UpdateChecker(opener=opener)
        result = UpdateCheckResult(
            status=STATUS_UPDATE_AVAILABLE,
            current_version="0.7.0",
            latest_version="0.8.0",
            asset=asset,
        )

        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(OSError):
                checker.download(result, destination=temp)
            self.assertEqual(list(Path(temp).iterdir()), [])


class TestInstallPlanning(unittest.TestCase):
    def _downloaded(self, temp, name="OpenLens-0.8.0-Linux", body=b"new build"):
        path = Path(temp) / name
        path.write_bytes(body)
        return path

    def _result(self):
        return UpdateCheckResult(
            status=STATUS_UPDATE_AVAILABLE,
            current_version="0.7.0",
            latest_version="0.8.0",
            release_url=RELEASE_URL,
            asset=ReleaseAsset(
                "OpenLens-0.8.0-Linux", "https://example.test/OpenLens-Linux", 9
            ),
        )

    def test_pip_or_dev_install_falls_back_to_release_page(self):
        installer = UpdateInstaller(frozen=False, system="Linux")
        self.assertFalse(installer.can_self_update())

        with tempfile.TemporaryDirectory() as temp:
            plan = installer.prepare(self._downloaded(temp), self._result())

        self.assertEqual(plan.kind, "release_page")
        self.assertEqual(plan.release_url, RELEASE_URL)

    def test_frozen_linux_build_prepares_a_replace_script(self):
        with tempfile.TemporaryDirectory() as temp:
            downloaded = self._downloaded(temp)
            executable = Path(temp) / "OpenLens"
            installer = UpdateInstaller(
                frozen=True, system="Linux", executable=executable, pid=4242
            )

            plan = installer.prepare(downloaded, self._result())

            self.assertEqual(plan.kind, "replace")
            self.assertEqual(plan.target, executable)
            script = plan.script.read_text(encoding="utf-8")
            self.assertIn("4242", script)
            self.assertIn(str(downloaded), script)
            self.assertIn(str(executable), script)
            self.assertIn("chmod +x", script)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux helper script")
    def test_linux_helper_replaces_the_executable_and_relaunches_it(self):
        with tempfile.TemporaryDirectory() as temp:
            downloaded = self._downloaded(temp)
            target = Path(temp) / "OpenLens"
            marker = Path(temp) / "relaunched.txt"
            new_content = (
                "#!/bin/sh\n" f"printf 'new version' > {shlex.quote(str(marker))}\n"
            )
            downloaded.write_text(new_content, encoding="utf-8")
            installer = UpdateInstaller(
                frozen=True, system="Linux", executable=target, pid=2**31 - 1
            )
            plan = installer.prepare(downloaded, self._result())

            subprocess.run(["/bin/sh", str(plan.script)], check=True, timeout=5)

            deadline = time.monotonic() + 3
            while not marker.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(marker.is_file())
            self.assertEqual(target.read_text(encoding="utf-8"), new_content)

    def test_frozen_windows_build_prepares_a_batch_script(self):
        with tempfile.TemporaryDirectory() as temp:
            downloaded = self._downloaded(temp, name="OpenLens-0.8.0-Windows.exe")
            executable = Path(temp) / "OpenLens.exe"
            installer = UpdateInstaller(
                frozen=True, system="Windows", executable=executable, pid=4242
            )

            plan = installer.prepare(downloaded, self._result())

            self.assertEqual(plan.kind, "replace")
            self.assertEqual(plan.script.suffix, ".bat")
            script = plan.script.read_text(encoding="utf-8")
            self.assertIn("tasklist", script)
            self.assertIn("4242", script)
            self.assertIn(str(downloaded), script)

    def test_frozen_macos_build_extracts_and_hands_off_the_app(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "OpenLens-0.8.0-macOS-arm64.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("OpenLens.app/Contents/Info.plist", "<plist/>")
                zf.writestr("OpenLens.app/Contents/MacOS/OpenLens", "binary")
            installer = UpdateInstaller(
                frozen=True,
                system="Darwin",
                executable=Path(temp) / "OpenLens",
                downloads_dir=Path(temp),
            )

            plan = installer.prepare(archive, self._result())

            self.assertEqual(plan.kind, "open_bundle")
            self.assertEqual(plan.app_path.name, "OpenLens.app")
            self.assertTrue((plan.app_path / "Contents" / "Info.plist").is_file())

    def test_macos_archive_cannot_escape_the_destination(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / "OpenLens-0.8.0-macOS-arm64.zip"
            with zipfile.ZipFile(archive, "w") as zf:
                zf.writestr("../escaped.txt", "outside")
            installer = UpdateInstaller(
                frozen=True,
                system="Darwin",
                executable=Path(temp) / "OpenLens",
                downloads_dir=Path(temp) / "Downloads",
            )

            with self.assertRaises(ValueError):
                installer.prepare(archive, self._result())

            self.assertFalse((Path(temp) / "escaped.txt").exists())


class TestInstallLaunch(unittest.TestCase):
    def test_linux_replace_starts_a_detached_helper(self):
        installer = UpdateInstaller(frozen=True, system="Linux")
        plan = InstallPlan(kind="replace", script=Path("/tmp/apply.sh"))

        with mock.patch("openlens.updater.subprocess.Popen") as popen:
            installer.launch(plan)

        command = popen.call_args.args[0]
        self.assertEqual(command, ["/bin/sh", "/tmp/apply.sh"])
        self.assertTrue(popen.call_args.kwargs["start_new_session"])

    def test_windows_replace_starts_a_hidden_batch_helper(self):
        installer = UpdateInstaller(frozen=True, system="Windows")
        plan = InstallPlan(kind="replace", script=Path("C:/Temp/apply.bat"))

        with mock.patch("openlens.updater.subprocess.Popen") as popen:
            installer.launch(plan)

        self.assertEqual(popen.call_args.args[0][:2], ["cmd.exe", "/c"])

    def test_macos_bundle_is_opened_with_the_desktop(self):
        installer = UpdateInstaller(frozen=True, system="Darwin")
        plan = InstallPlan(kind="open_bundle", app_path=Path("/tmp/OpenLens.app"))

        with mock.patch("openlens.updater.subprocess.Popen") as popen:
            installer.launch(plan)

        self.assertEqual(popen.call_args.args[0], ["open", "/tmp/OpenLens.app"])

    def test_release_page_plan_cannot_be_launched(self):
        installer = UpdateInstaller(frozen=False, system="Linux")
        with self.assertRaises(ValueError):
            installer.launch(InstallPlan(kind="release_page"))


if __name__ == "__main__":
    unittest.main()
