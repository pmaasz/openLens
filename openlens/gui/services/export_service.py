"""Window-independent orchestration of user-initiated exports.

The main window keeps the file dialogs, status messages and error boxes. This
module wraps the active model, calls the exporter and writes the file. It must
not import Qt: the orchestration is tested headlessly, and the GUI package
already degrades gracefully when PySide6 is missing.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from openlens.io.export import ISO10110Generator
from openlens.io.step_export import StepExporter
from openlens.lens import Lens, json_safe_radii
from openlens.optical_system import OpticalSystem, as_system
from openlens.stl_export import export_lens_stl


@dataclass(frozen=True)
class ExportResult:
    """Outcome of one export attempt.

    The window maps this to its existing user-facing messages; ``error`` is
    the original exception text, without a "Failed to export..." prefix.

    Attributes:
        ok: Whether the file was written.
        kind: Exporter identifier (``json``, ``stl``, ``step``, ``iso10110``
            or ``report``).
        path: Destination path as supplied by the caller.
        bytes_written: Size of the written file, or 0 on failure.
        details: Exporter-specific data (STL triangle count, STEP summary).
        error: Exception text on failure, otherwise ``None``.
        dependency_missing: True when the failure was an ``ImportError``, so
            the window can show the dependency hint instead of a generic
            error.
        warnings: Human-readable notes about parts omitted from the file.
    """

    ok: bool
    kind: str
    path: str
    bytes_written: int = 0
    details: Mapping[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    dependency_missing: bool = False
    warnings: Tuple[str, ...] = ()

    @property
    def partial(self) -> bool:
        """Whether the file was written but some parts were skipped."""
        return bool(self.warnings)


def _suggest_housing(system: Any) -> List[Dict[str, Any]]:
    """Build the default STEP housing, importing the designer lazily.

    The import stays inside the function so an ``ImportError`` from an
    optional CAD dependency is classified by :meth:`ExportService.export_step`
    rather than breaking module import.
    """
    from openlens.mechanical_designer import MechanicalDesigner

    return MechanicalDesigner(system).suggest_housing()


class ExportService:
    """Run exports without a window, dialog or Qt event loop."""

    def __init__(
        self,
        *,
        clock: Callable[[], datetime] = datetime.now,
        housing_factory: Optional[Callable[[Any], List[Dict[str, Any]]]] = None,
    ) -> None:
        """Create the service.

        Args:
            clock: Timestamp source for the text report. Injected by tests so
                the report is deterministic.
            housing_factory: Builds STEP housing parts from an
                ``OpticalSystem``. Defaults to
                ``MechanicalDesigner(...).suggest_housing()``; tests can pass
                a stub to skip the mechanical design step.
        """
        self._clock = clock
        self._housing_factory = housing_factory or _suggest_housing

    def save_lens_json(self, lens: Lens, path: str) -> ExportResult:
        """Write the lens in the File > Save As JSON format.

        Args:
            lens: Lens to serialize.
            path: Destination file.

        Returns:
            The export result.
        """
        try:
            with open(path, "w") as handle:
                # A flat surface is an infinite radius in the model and null in
                # JSON: the bare ``Infinity`` literal is not valid JSON and the
                # importer rejects it, so a plano lens could never be imported
                # again. ``allow_nan=False`` fails the export instead of
                # writing a file that cannot be read.
                json.dump(json_safe_radii(lens.to_dict()), handle, indent=2, allow_nan=False)
            return self._success("json", path)
        except Exception as exc:
            return self._failure("json", path, exc)

    def save_system_json(self, system: OpticalSystem, path: str) -> ExportResult:
        """Write an assembly in the File > Save As JSON interchange format.

        ``OpticalSystem.save()`` wrote the same document, but it swallowed the
        exception and returned a bool, so the window could not report why an
        export failed. This mirrors ``save_lens_json`` and keeps the failure
        text.

        Args:
            system: Assembly to serialize.
            path: Destination file.

        Returns:
            The export result.
        """
        try:
            with open(path, "w") as handle:
                json.dump(
                    json_safe_radii(system.to_dict()),
                    handle,
                    indent=2,
                    allow_nan=False,
                )
            return self._success("json", path)
        except Exception as exc:
            return self._failure("json", path, exc)

    def export_stl(self, target: Any, path: str, *, resolution: int = 50) -> ExportResult:
        """Export a lens or assembly to STL.

        Args:
            target: Lens or OpticalSystem to export.
            path: Destination file.
            resolution: Surface sampling resolution passed to the exporter.

        Returns:
            The export result; ``details["triangles"]`` is the triangle count.
        """
        try:
            system = as_system(target)
            triangles = export_lens_stl(system, path, resolution=resolution)
            return self._success("stl", path, {"triangles": triangles})
        except Exception as exc:
            return self._failure("stl", path, exc)

    def export_step(self, target: Any, path: str) -> ExportResult:
        """Export a lens or assembly to STEP with the suggested housing.

        Args:
            target: Lens or OpticalSystem to export.
            path: Destination file.

        Returns:
            The export result; ``details`` is the exporter summary
            (``shapes``, ``skipped``, ``skipped_parts``). A missing optional
            dependency sets ``dependency_missing`` instead of raising.
        """
        try:
            system = as_system(target)
            housing = self._housing_factory(system)
            summary = StepExporter(system).export(path, housing=housing)
            details = summary if isinstance(summary, dict) else {}
            skipped_parts = details.get("skipped_parts") or []
            warnings = tuple(
                f"{part} was skipped and is missing from the STEP file" for part in skipped_parts
            )
            if details.get("skipped") and not warnings:
                warnings = ("one or more parts were skipped and are missing from the STEP file",)
            return self._success("step", path, details, warnings=warnings)
        except ImportError as exc:
            return self._failure("step", path, exc, dependency_missing=True)
        except Exception as exc:
            return self._failure("step", path, exc)

    def export_iso10110(
        self, target: Any, path: str, *, width: int = 800, height: int = 600
    ) -> ExportResult:
        """Render an ISO 10110 drawing as SVG.

        Args:
            target: Lens or OpticalSystem to draw.
            path: Destination file.
            width: Drawing width in pixels.
            height: Drawing height in pixels.

        Returns:
            The export result.
        """
        try:
            system = as_system(target)
            ISO10110Generator(system).generate_svg(path, width=width, height=height)
            return self._success("iso10110", path)
        except Exception as exc:
            return self._failure("iso10110", path, exc)

    def export_report(self, target: Any, path: str) -> ExportResult:
        """Write the window's text design report.

        Args:
            target: Lens or OpticalSystem to report on.
            path: Destination file.

        Returns:
            The export result.
        """
        try:
            with open(path, "w") as handle:
                handle.write("OpenLens Design Report\n")
                handle.write("======================\n\n")
                handle.write(f"Name: {target.name}\n")
                handle.write(f"Date: {self._clock().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                if isinstance(target, Lens):
                    handle.write("Type: Single Lens Element\n")
                    handle.write(f"Radius 1: {target.radius_of_curvature_1} mm\n")
                    handle.write(f"Radius 2: {target.radius_of_curvature_2} mm\n")
                    handle.write(f"Thickness: {target.thickness} mm\n")
                    handle.write(f"Diameter: {target.diameter} mm\n")
                    handle.write(f"Material: {target.material} (n={target.refractive_index})\n")
                else:
                    handle.write(f"Type: Optical Assembly ({len(target.elements)} elements)\n")
                    for index, element in enumerate(target.elements):
                        handle.write(f"\nElement {index + 1}: {element.lens.name}\n")
                        handle.write(f"  Position: {element.position} mm\n")
                        handle.write(f"  Thickness: {element.lens.thickness} mm\n")
                        handle.write(f"  Material: {element.lens.material}\n")

            return self._success("report", path)
        except Exception as exc:
            return self._failure("report", path, exc)

    @staticmethod
    def _success(
        kind: str,
        path: str,
        details: Optional[Mapping[str, Any]] = None,
        warnings: Sequence[str] = (),
    ) -> ExportResult:
        """Build a successful result, measuring the file that was written."""
        try:
            size = Path(path).stat().st_size
        except OSError:
            size = 0
        return ExportResult(
            ok=True,
            kind=kind,
            path=path,
            bytes_written=size,
            details=details or {},
            warnings=tuple(warnings),
        )

    @staticmethod
    def _failure(
        kind: str, path: str, error: BaseException, *, dependency_missing: bool = False
    ) -> ExportResult:
        """Build a failed result from the caught exception."""
        return ExportResult(
            ok=False,
            kind=kind,
            path=path,
            error=str(error),
            dependency_missing=dependency_missing,
        )
