"""Mechanical materials for lens casings.

Kept separate from the optical glass catalog: a casing cares about thermal
expansion, density and opacity, not refractive index. Standard entries are
fixed; user-defined entries live in a JSON file under the user data directory
so every assembly can reuse them.
"""

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .atomic import atomic_write_json
from .paths import default_mechanical_materials_path

logger = logging.getLogger(__name__)

PathLike = Union[str, Path]

#: Fixed mechanical materials, in the order shown in the UI.
STANDARD_MATERIALS: Dict[str, Dict[str, Any]] = {
    "Aluminium": {"cte": 23.6e-6, "density": 2.70, "opaque": True},
    "Brass": {"cte": 19.0e-6, "density": 8.50, "opaque": True},
    "Steel": {"cte": 12.0e-6, "density": 7.85, "opaque": True},
    "Titanium": {"cte": 8.6e-6, "density": 4.43, "opaque": True},
    "Plastic (ABS)": {"cte": 90.0e-6, "density": 1.04, "opaque": True},
}


class MechanicalMaterialCatalog:
    """Standard casing materials plus the user's custom entries."""

    STANDARD_MATERIALS = STANDARD_MATERIALS

    def __init__(self, path: Optional[PathLike] = None) -> None:
        self.path = (
            Path(path).expanduser() if path is not None else default_mechanical_materials_path()
        )
        self._custom: Dict[str, Dict[str, Any]] = {}
        self.load_custom_materials()

    def get_available_materials(self) -> Dict[str, Dict[str, Any]]:
        """Return every material, standard first, with a ``custom`` marker."""
        materials = {
            name: {**spec, "custom": False} for name, spec in self.STANDARD_MATERIALS.items()
        }
        for name, spec in self._custom.items():
            materials[name] = {**spec, "custom": True}
        return materials

    def get_material(self, name: str) -> Optional[Dict[str, Any]]:
        """Look up one material by name."""
        if name in self.STANDARD_MATERIALS:
            return {**self.STANDARD_MATERIALS[name], "custom": False}
        if name in self._custom:
            return {**self._custom[name], "custom": True}
        return None

    def add_custom_material(
        self, name: str, cte: float, density: float, opaque: bool = True
    ) -> Dict[str, Any]:
        """Add or replace a user-defined material.

        Raises:
            ValueError: If the name is blank or reserved, or a property is
                not finite and non-negative.
        """
        clean = str(name).strip()
        if not clean:
            raise ValueError("Material name must not be blank")
        if clean.lower() in {standard.lower() for standard in self.STANDARD_MATERIALS}:
            raise ValueError(f"{clean!r} is a standard material and cannot be redefined")
        spec = self._normalize(cte, density, opaque)
        self._custom[clean] = spec
        return {**spec, "custom": True}

    def remove_custom_material(self, name: str) -> bool:
        """Remove a user-defined material from memory."""
        if name not in self._custom:
            return False
        del self._custom[name]
        return True

    def save_custom_materials(self) -> Path:
        """Write custom materials to :attr:`path`."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(self.path, {"custom_materials": self._custom})
        logger.info("Saved %d custom material(s) to %s", len(self._custom), self.path)
        return self.path

    def load_custom_materials(self) -> Dict[str, Dict[str, Any]]:
        """Reload custom materials, skipping malformed entries."""
        self._custom = {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("Ignoring mechanical material catalog %s: %s", self.path, exc)
            return {}
        if not isinstance(payload, dict):
            logger.warning("Ignoring mechanical material catalog %s: expected an object", self.path)
            return {}
        entries = payload.get("custom_materials", payload)
        if not isinstance(entries, dict):
            return {}
        reserved = {name.lower() for name in self.STANDARD_MATERIALS}
        for raw_name, raw_spec in entries.items():
            name = str(raw_name).strip()
            if not name or name.lower() in reserved or not isinstance(raw_spec, dict):
                continue
            try:
                self._custom[name] = self._normalize(
                    raw_spec.get("cte"),
                    raw_spec.get("density"),
                    bool(raw_spec.get("opaque", True)),
                )
            except (TypeError, ValueError) as exc:
                logger.warning("Ignoring invalid material %r: %s", name, exc)
        return {name: dict(spec) for name, spec in self._custom.items()}

    @staticmethod
    def _normalize(cte: Any, density: Any, opaque: Any) -> Dict[str, Any]:
        try:
            cte_value = float(cte)
            density_value = float(density)
        except (TypeError, ValueError) as exc:
            raise ValueError("Material CTE and density must be numbers") from exc
        if not math.isfinite(cte_value) or cte_value < 0:
            raise ValueError(f"CTE must be a finite, non-negative number, got {cte_value}")
        if not math.isfinite(density_value) or density_value < 0:
            raise ValueError(f"Density must be a finite, non-negative number, got {density_value}")
        return {"cte": cte_value, "density": density_value, "opaque": bool(opaque)}


_catalog: Optional[MechanicalMaterialCatalog] = None


def get_mechanical_material_catalog() -> MechanicalMaterialCatalog:
    """Return the process-wide material catalog."""
    global _catalog
    if _catalog is None:
        _catalog = MechanicalMaterialCatalog()
    return _catalog


def reset_mechanical_material_catalog() -> None:
    """Drop the cached catalog so a new path/environment is picked up."""
    global _catalog
    _catalog = None
