"""Model Context Protocol (MCP) server for OpenLens.

The server exposes the lens database, the preset library and the performance
calculators as MCP tools, so an AI client can list, create and analyse lenses
from the same SQLite store the GUI uses.

Only the optional ``mcp`` package is required. Install it with::

    pip install "openlens[mcp]"

Run the stdio server with either command::

    python -m openlens.mcp_server
    python -m openlens.lens_editor mcp
"""

import logging
import math
from typing import Any, Dict, List, Optional, cast

from .database import DatabaseManager
from .lens import Lens, json_safe_radii
from .performance_metrics import PerformanceMetrics
from .preset_library import get_preset_library
from .validation import (
    validate_diameter,
    validate_lens_name,
    validate_radius,
    validate_refractive_index,
    validate_thickness,
)

logger = logging.getLogger(__name__)

try:
    from mcp.server.fastmcp import FastMCP

    MCP_AVAILABLE = True
except ImportError:  # pragma: no cover - the guard is covered by tests
    FastMCP = None  # type: ignore[assignment]
    MCP_AVAILABLE = False


class OpenLensTools:
    """Plain-Python operations exposed by the MCP server.

    Keeping the operations independent of the optional ``mcp`` package makes
    them testable in environments where that dependency is not installed.
    """

    def __init__(self, database: Optional[DatabaseManager] = None) -> None:
        """Create the tool set.

        Args:
            database: Database to read and write. Defaults to the application
                database resolved by :class:`DatabaseManager`.
        """
        self._database = database or DatabaseManager()

    def _all_lenses(self) -> List[Dict[str, Any]]:
        """Return only standalone lenses, not assembly members or systems."""
        return [row for row in self._database.load_all() if row.get("row_type") == "Lens"]

    def list_lenses(self) -> List[Dict[str, Any]]:
        """List every standalone lens stored in the database."""
        return [cast(Dict[str, Any], json_safe_radii(row)) for row in self._all_lenses()]

    def get_lens(self, lens_id: str) -> Optional[Dict[str, Any]]:
        """Return one lens by id, or ``None`` when it does not exist."""
        for row in self._all_lenses():
            if str(row.get("id")) == str(lens_id):
                return cast(Dict[str, Any], json_safe_radii(row))
        return None

    def create_lens(
        self,
        name: str,
        radius_of_curvature_1: float,
        radius_of_curvature_2: float,
        thickness: float,
        diameter: float,
        refractive_index: Optional[float] = None,
        material: str = "BK7",
    ) -> Dict[str, Any]:
        """Validate, create and persist a lens.

        A radius of ``0`` or ``inf`` is a flat surface. Invalid values raise
        :class:`~openlens.validation.ValidationError` before anything is
        written. When ``refractive_index`` is omitted it is resolved from
        ``material`` in the glass catalogue.
        """
        lens = Lens.for_material(
            material,
            name=validate_lens_name(name),
            radius_of_curvature_1=validate_radius(radius_of_curvature_1, allow_flat=True),
            radius_of_curvature_2=validate_radius(radius_of_curvature_2, allow_flat=True),
            thickness=validate_thickness(thickness),
            diameter=validate_diameter(diameter),
            refractive_index=(
                None if refractive_index is None else validate_refractive_index(refractive_index)
            ),
        )
        self._database.save_lens(lens.to_dict())

        stored = self.get_lens(lens.id)
        if stored is None:
            raise RuntimeError("the lens was saved but could not be read back")
        return stored

    def delete_lens(self, lens_id: str) -> bool:
        """Delete a lens; return ``False`` when it was not found."""
        if self.get_lens(lens_id) is None:
            return False
        self._database.delete_item(lens_id)
        return True

    def calculate_metrics(self, lens_id: str) -> Optional[Dict[str, Any]]:
        """Return the performance metrics for a stored lens.

        Non-finite values are reported as ``None``: JSON has no spelling for
        infinity, and a client should see a missing measurement rather than
        an invalid literal.
        """
        row = self.get_lens(lens_id)
        if row is None:
            return None

        metrics = PerformanceMetrics(Lens.from_dict(row)).get_all_metrics()
        return {
            key: (None if isinstance(value, float) and not math.isfinite(value) else value)
            for key, value in metrics.items()
        }

    def list_presets(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List the built-in lens presets, optionally filtered by category."""
        return [
            {
                "name": preset.name,
                "category": preset.category,
                "description": preset.description,
                "manufacturer": preset.manufacturer,
                "part_number": preset.part_number,
                "typical_use": preset.typical_use,
            }
            for preset in get_preset_library().list_presets(category)
        ]

    def load_preset(self, name: str, save: bool = False) -> Optional[Dict[str, Any]]:
        """Return a copy of a preset lens.

        Args:
            name: Exact preset name as returned by :meth:`list_presets`.
            save: When true, also store the copy in the database.
        """
        preset_lens = get_preset_library().get_lens_copy(name)
        if preset_lens is None:
            return None

        if not save:
            return cast(Dict[str, Any], json_safe_radii(preset_lens.to_dict()))

        self._database.save_lens(preset_lens.to_dict())
        stored = self.get_lens(preset_lens.id)
        if stored is None:
            raise RuntimeError("the preset was saved but could not be read back")
        return stored


def create_server(tools: Optional[OpenLensTools] = None) -> Any:
    """Create the MCP server and register the OpenLens tools.

    Args:
        tools: Tool set to expose. Defaults to a database-backed instance.

    Returns:
        A configured ``FastMCP`` server.

    Raises:
        ImportError: If the optional ``mcp`` package is not installed.
    """
    if not MCP_AVAILABLE or FastMCP is None:
        raise ImportError(
            "The MCP server requires the optional 'mcp' package. "
            "Install it with: pip install 'openlens[mcp]'"
        )

    operations = tools or OpenLensTools()
    server = FastMCP("openLens")

    @server.tool()
    def list_lenses() -> List[Dict[str, Any]]:
        """List every standalone lens stored in OpenLens."""
        return operations.list_lenses()

    @server.tool()
    def get_lens(lens_id: str) -> Optional[Dict[str, Any]]:
        """Return one lens by id, or null when no such lens exists."""
        return operations.get_lens(lens_id)

    @server.tool()
    def create_lens(
        name: str,
        radius_of_curvature_1: float,
        radius_of_curvature_2: float,
        thickness: float,
        diameter: float,
        refractive_index: Optional[float] = None,
        material: str = "BK7",
    ) -> Dict[str, Any]:
        """Create and persist a lens; 0 or inf is a flat surface."""
        return operations.create_lens(
            name=name,
            radius_of_curvature_1=radius_of_curvature_1,
            radius_of_curvature_2=radius_of_curvature_2,
            thickness=thickness,
            diameter=diameter,
            refractive_index=refractive_index,
            material=material,
        )

    @server.tool()
    def delete_lens(lens_id: str) -> bool:
        """Delete a lens by id; returns false when it was not found."""
        return operations.delete_lens(lens_id)

    @server.tool()
    def calculate_metrics(lens_id: str) -> Optional[Dict[str, Any]]:
        """Calculate focal length, f-number, Airy disk and resolution metrics."""
        return operations.calculate_metrics(lens_id)

    @server.tool()
    def list_presets(category: Optional[str] = None) -> List[Dict[str, Any]]:
        """List built-in lens presets, optionally filtered by category."""
        return operations.list_presets(category)

    @server.tool()
    def load_preset(name: str, save: bool = False) -> Optional[Dict[str, Any]]:
        """Load a preset lens; set save=true to store a copy in the database."""
        return operations.load_preset(name, save)

    return server


def main() -> int:
    """Run the stdio MCP server.

    Returns:
        Process exit code. A missing optional dependency is reported on
        stderr and returns 1 instead of raising.
    """
    if not MCP_AVAILABLE:
        logger.error(
            "The MCP server requires the optional 'mcp' package. "
            "Install it with: pip install 'openlens[mcp]'"
        )
        return 1

    create_server().run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
