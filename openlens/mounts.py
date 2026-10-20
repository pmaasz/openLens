"""Lens mount standards and user-defined mount persistence.

A camera mount is described by its flange distance - the distance from the
mounting face to the sensor/film plane - plus, for threaded mounts, a thread
diameter and pitch. The standard table is fixed; custom mounts are a user
setting stored separately from the lens library so they can be shared by every
lens and survive application upgrades.
"""

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .atomic import atomic_write_json
from .paths import default_mounts_path

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

#: Standard mounts, in the order shown in the UI. Bayonet mounts have no
#: thread, so their diameter and pitch are zero.
STANDARD_MOUNTS: Dict[str, Dict[str, float]] = {
    "C-mount": {"thread_diameter": 25.4, "thread_pitch": 0.794, "flange_distance": 17.526},
    "CS-mount": {"thread_diameter": 25.4, "thread_pitch": 0.794, "flange_distance": 12.526},
    "M42": {"thread_diameter": 42.0, "thread_pitch": 1.0, "flange_distance": 45.46},
    "M39": {"thread_diameter": 39.0, "thread_pitch": 1.0, "flange_distance": 28.8},
    "T-mount": {"thread_diameter": 42.0, "thread_pitch": 0.75, "flange_distance": 55.0},
    "X-mount": {"thread_diameter": 0.0, "thread_pitch": 0.0, "flange_distance": 17.7},
    "M-mount": {"thread_diameter": 0.0, "thread_pitch": 0.0, "flange_distance": 27.8},
    "EF-mount": {"thread_diameter": 54.0, "thread_pitch": 1.0, "flange_distance": 44.0},
    "F-mount": {"thread_diameter": 44.0, "thread_pitch": 1.0, "flange_distance": 46.5},
}


class MountCatalog:
    """Standard mounts plus the user's custom mounts.

    Args:
        path: Custom-mount JSON file. None uses
            :func:`openlens.paths.default_mounts_path`.

    The catalog is loaded in the constructor. A missing config file is normal;
    a corrupt one is logged and ignored so it cannot prevent the application
    from starting or hide the standard mounts.
    """

    STANDARD_MOUNTS = STANDARD_MOUNTS

    def __init__(self, path: Optional[PathLike] = None) -> None:
        self.path = Path(path).expanduser() if path is not None else default_mounts_path()
        self._custom_mounts: Dict[str, Dict[str, Any]] = {}
        self.load_custom_mounts()

    def get_available_mounts(self) -> Dict[str, Dict[str, Any]]:
        """Return every mount, standard first, as independent dictionaries.

        Returns:
            Mount name mapped to its thread/flange specification. ``custom``
            distinguishes user-defined entries from the fixed table.
        """
        available: Dict[str, Dict[str, Any]] = {}
        for name, spec in self.STANDARD_MOUNTS.items():
            available[name] = {**spec, "custom": False}
        for name, spec in self._custom_mounts.items():
            available[name] = {**spec, "custom": True}
        return available

    def get_mount(self, name: str) -> Optional[Dict[str, Any]]:
        """Look up one mount.

        Args:
            name: Mount name, case-sensitive.

        Returns:
            A copy of the mount specification, or None if it is unknown.
        """
        if name in self.STANDARD_MOUNTS:
            return {**self.STANDARD_MOUNTS[name], "custom": False}
        if name in self._custom_mounts:
            return {**self._custom_mounts[name], "custom": True}
        return None

    def get_flange_distance(self, name: str) -> Optional[float]:
        """Flange distance of a mount in mm, or None if it is unknown."""
        spec = self.get_mount(name)
        return float(spec["flange_distance"]) if spec is not None else None

    def add_custom_mount(
        self,
        name: str,
        flange_distance: float,
        thread_diameter: float = 0.0,
        thread_pitch: float = 0.0,
    ) -> Dict[str, Any]:
        """Add or replace a user-defined mount.

        Args:
            name: Unique display name. It may not shadow a standard mount.
            flange_distance: Mounting face to sensor plane (mm); must be > 0.
            thread_diameter: Thread major diameter (mm); 0 for a bayonet.
            thread_pitch: Thread pitch (mm); 0 for a bayonet.

        Returns:
            A copy of the stored specification.

        Raises:
            ValueError: If the name is blank or reserved, or a dimension is
                not a finite, non-negative (flange: positive) number.
        """
        clean_name = str(name).strip()
        if not clean_name:
            raise ValueError("Mount name must not be blank")
        if clean_name.lower() in {standard.lower() for standard in self.STANDARD_MOUNTS}:
            raise ValueError(f"{clean_name!r} is a standard mount and cannot be redefined")

        spec = self._normalize_spec(flange_distance, thread_diameter, thread_pitch)
        self._custom_mounts[clean_name] = spec
        return {**spec, "custom": True}

    def remove_custom_mount(self, name: str) -> bool:
        """Remove a user-defined mount.

        Standard mounts are part of the application and cannot be removed.
        The change is in memory until :meth:`save_custom_mounts` is called.

        Returns:
            True if a custom mount was removed, False otherwise.
        """
        if name not in self._custom_mounts:
            return False
        del self._custom_mounts[name]
        return True

    def save_custom_mounts(self) -> Path:
        """Write the custom mounts to :attr:`path`.

        Returns:
            The path written.

        Raises:
            OSError: If the directory or file cannot be written.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"custom_mounts": self._custom_mounts}
        atomic_write_json(self.path, payload)
        logger.info("Saved %d custom mount(s) to %s", len(self._custom_mounts), self.path)
        return self.path

    def load_custom_mounts(self) -> Dict[str, Dict[str, Any]]:
        """Reload custom mounts from :attr:`path`.

        A missing file clears the in-memory custom list. Malformed files and
        individual invalid entries are logged and skipped; standard mounts are
        never affected.

        Returns:
            A copy of the loaded custom-mount mapping.
        """
        self._custom_mounts = {}
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {}
        except OSError as exc:
            logger.warning("Could not read mount configuration %s: %s", self.path, exc)
            return {}

        try:
            payload = json.loads(raw)
        except (TypeError, ValueError) as exc:
            logger.warning("Ignoring malformed mount configuration %s: %s", self.path, exc)
            return {}

        if not isinstance(payload, dict):
            logger.warning("Ignoring mount configuration %s: expected an object", self.path)
            return {}
        entries = payload.get("custom_mounts", payload)
        if not isinstance(entries, dict):
            logger.warning("Ignoring mount configuration %s: bad custom_mounts", self.path)
            return {}

        standard_names = {name.lower() for name in self.STANDARD_MOUNTS}
        for raw_name, raw_spec in entries.items():
            name = str(raw_name).strip()
            if not name or name.lower() in standard_names:
                logger.warning("Ignoring reserved mount name in %s: %r", self.path, raw_name)
                continue
            if not isinstance(raw_spec, dict):
                logger.warning("Ignoring mount %r in %s: expected an object", name, self.path)
                continue
            try:
                spec = self._normalize_spec(
                    raw_spec.get("flange_distance"),
                    raw_spec.get("thread_diameter", 0.0),
                    raw_spec.get("thread_pitch", 0.0),
                )
            except (TypeError, ValueError) as exc:
                logger.warning("Ignoring invalid mount %r in %s: %s", name, self.path, exc)
                continue
            self._custom_mounts[name] = spec

        return {name: dict(spec) for name, spec in self._custom_mounts.items()}

    @staticmethod
    def _normalize_spec(
        flange_distance: Any, thread_diameter: Any, thread_pitch: Any
    ) -> Dict[str, float]:
        """Validate and normalize one mount specification."""
        try:
            flange = float(flange_distance)
            diameter = float(thread_diameter or 0.0)
            pitch = float(thread_pitch or 0.0)
        except (TypeError, ValueError) as exc:
            raise ValueError("Mount dimensions must be numbers") from exc

        if not math.isfinite(flange) or flange <= 0:
            raise ValueError(f"Flange distance must be a positive finite number, got {flange}")
        for label, value in (("thread diameter", diameter), ("thread pitch", pitch)):
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{label} must be a finite, non-negative number, got {value}")

        return {
            "thread_diameter": diameter,
            "thread_pitch": pitch,
            "flange_distance": flange,
        }
