"""Aperture stop shapes: circular, polygonal iris blades, obscuration, vanes.

The stop's diameter is the circumscribed size. A regular polygon with ``N``
blades still passes the circle inscribed in it, of radius
``diameter / 2 * cos(pi / N)`` - so a six-blade stop does not clip the centre
of the beam, only its corners. An annular stop removes a central hole, and
optional spider vanes remove narrow strips through the centre.

The shape is deliberately numerical and numpy-free: the 2D and 3D tracers clip
individual rays with it, and the wavefront sensor turns it into a pupil mask.
"""

import math
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: Boundary tolerance in mm, matching the tracers' existing stop tolerance.
BOUNDARY_TOLERANCE_MM = 1e-9


@dataclass(frozen=True)
class ApertureShape:
    """The opening of an aperture stop.

    Attributes:
        blades: Number of straight iris blades; 0 means a circle.
        rotation_deg: Polygon/vanes rotation about the optical axis.
        obscuration_ratio: Central obstruction radius as a fraction of the
            stop radius, in ``[0, 1)``; 0 leaves no hole.
        spider_vanes: Number of diametral vanes through the centre; 0 is none.
        spider_width_mm: Full width of each vane in mm; 0 leaves none.
    """

    blades: int = 0
    rotation_deg: float = 0.0
    obscuration_ratio: float = 0.0
    spider_vanes: int = 0
    spider_width_mm: float = 0.0

    def __post_init__(self) -> None:
        """Reject a shape the tracers cannot represent."""
        if not isinstance(self.blades, int) or (self.blades != 0 and self.blades < 3):
            raise ValueError("aperture blades must be 0 or at least 3")
        if not math.isfinite(self.rotation_deg):
            raise ValueError("aperture rotation must be finite")
        if not 0.0 <= self.obscuration_ratio < 1.0:
            raise ValueError("aperture obscuration ratio must be in [0, 1)")
        if not isinstance(self.spider_vanes, int) or self.spider_vanes < 0:
            raise ValueError("spider vane count must be a non-negative integer")
        if not math.isfinite(self.spider_width_mm) or self.spider_width_mm < 0:
            raise ValueError("spider vane width must be non-negative and finite")

    @property
    def is_circular(self) -> bool:
        """Whether the opening is a plain circle the old code path can use."""
        return self.blades == 0 and self.obscuration_ratio == 0.0 and self.spider_vanes == 0

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "ApertureShape":
        """Build a shape from its serialized form (missing keys default)."""
        if not data:
            return cls()
        if not isinstance(data, dict):
            raise TypeError("aperture stop shape must be a mapping")
        return cls(
            blades=int(data.get("blades", 0) or 0),
            rotation_deg=float(data.get("rotation_deg", 0.0) or 0.0),
            obscuration_ratio=float(data.get("obscuration_ratio", 0.0) or 0.0),
            spider_vanes=int(data.get("spider_vanes", 0) or 0),
            spider_width_mm=float(data.get("spider_width_mm", 0.0) or 0.0),
        )

    @classmethod
    def from_stop(cls, stop: Optional[Dict[str, Any]]) -> "ApertureShape":
        """Build a shape from an ``OpticalSystem.get_aperture_stop()`` dict."""
        if not stop:
            return cls()
        shape = stop.get("shape")
        if isinstance(shape, cls):
            return shape
        if isinstance(shape, dict):
            return cls.from_dict(shape)
        return cls()

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the shape into JSON-compatible scalars."""
        return {
            "blades": self.blades,
            "rotation_deg": self.rotation_deg,
            "obscuration_ratio": self.obscuration_ratio,
            "spider_vanes": self.spider_vanes,
            "spider_width_mm": self.spider_width_mm,
        }

    def label(self) -> str:
        """A short human-readable description for lists and drawings."""
        if self.blades >= 3:
            text = f"{self.blades}-blade"
        else:
            text = "Circular"
        if self.obscuration_ratio > 0.0:
            text += f", {self.obscuration_ratio * 100:.0f}% obscured"
        if self.spider_vanes > 0 and self.spider_width_mm > 0.0:
            text += f", {self.spider_vanes} spider vane(s)"
        return text

    def boundary_radius(self, theta_rad: float, radius_mm: float) -> float:
        """Distance from the centre to the opening edge at ``theta_rad``.

        For a polygon this is the flat-to-flat distance divided by the cosine
        of the angle from the nearest edge midpoint; for a circle it is the
        radius itself.
        """
        if self.blades < 3 or radius_mm <= 0.0:
            return radius_mm
        sector = 2.0 * math.pi / self.blades
        offset = (theta_rad - math.radians(self.rotation_deg)) % sector
        inradius = radius_mm * math.cos(math.pi / self.blades)
        return inradius / math.cos(offset - math.pi / self.blades)

    def inner_radius(self, radius_mm: float) -> float:
        """Radius of the central obstruction, in mm."""
        return radius_mm * self.obscuration_ratio

    def contains(
        self, y_mm: float, z_mm: float, radius_mm: float, include_spiders: bool = True
    ) -> bool:
        """Whether a point on the stop plane passes the opening.

        Args:
            y_mm: Tangential coordinate.
            z_mm: Sagittal coordinate.
            radius_mm: Circumscribed stop radius.
            include_spiders: Set False for a meridional 2D trace, which cannot
                represent vanes running out of its plane.

        Returns:
            True when the point is inside the opening and outside the central
            obstruction, clear of every vane and inside the polygon.
        """
        radius_mm = abs(float(radius_mm))
        r_squared = y_mm * y_mm + z_mm * z_mm
        outer = radius_mm + BOUNDARY_TOLERANCE_MM
        if r_squared > outer * outer:
            return False

        hole = self.inner_radius(radius_mm) - BOUNDARY_TOLERANCE_MM
        if hole > 0.0 and r_squared < hole * hole:
            return False

        if self.blades >= 3:
            theta = math.atan2(z_mm, y_mm)
            if (
                math.sqrt(r_squared)
                > self.boundary_radius(theta, radius_mm) + BOUNDARY_TOLERANCE_MM
            ):
                return False

        if include_spiders and self.spider_vanes > 0 and self.spider_width_mm > 0.0:
            half_width = self.spider_width_mm / 2.0 + BOUNDARY_TOLERANCE_MM
            for index in range(self.spider_vanes):
                angle = math.radians(self.rotation_deg) + index * math.pi / self.spider_vanes
                # Distance from the point to the vane line through the centre.
                if abs(-y_mm * math.sin(angle) + z_mm * math.cos(angle)) <= half_width:
                    return False

        return True

    def pupil_mask(
        self, Y: Iterable[Iterable[float]], Z: Iterable[Iterable[float]], radius_mm: float
    ) -> List[List[bool]]:
        """Boolean mask for a pupil grid, in the same shape as ``Y``/``Z``."""
        return [
            [self.contains(y, z, radius_mm) for y, z in zip(y_row, z_row)]
            for y_row, z_row in zip(Y, Z)
        ]

    def outline(self, radius_mm: float, points: int = 72) -> List[Tuple[float, float]]:
        """Closed outline of the outer opening, for drawing.

        A polygon returns its vertices; a circle returns ``points`` samples.
        """
        if self.blades >= 3:
            start = math.radians(self.rotation_deg)
            step = 2.0 * math.pi / self.blades
            return [
                (radius_mm * math.cos(start + i * step), radius_mm * math.sin(start + i * step))
                for i in range(self.blades)
            ]
        return [
            (
                radius_mm * math.cos(2.0 * math.pi * i / points),
                radius_mm * math.sin(2.0 * math.pi * i / points),
            )
            for i in range(points)
        ]
