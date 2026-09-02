"""
Core ray classes and optical intersection math for ray tracing.

Provides:
- RefractionResult enum
- OpticalIntersector (Snell's law, sphere intersection)
- Ray (2D) and Ray3D (3D with polarization)
"""

import math
import enum
from typing import List, Optional, Tuple, Any

from .vector3 import Vector3, vec3
from .constants import (
    EPSILON,
    WAVELENGTH_GREEN,
    NM_TO_MM,
    REFRACTIVE_INDEX_AIR,
)

try:
    import numpy as np
    from .polarization import PolarizationCalculator

    HAS_POLARIZATION = True
except ImportError:
    np = None
    PolarizationCalculator = None
    HAS_POLARIZATION = False


class RefractionResult(enum.Enum):
    """Outcome of applying Snell's law at an interface."""

    REFRACTED = "refracted"  # transmitted into new medium; n updated
    REFLECTED = "reflected"  # total internal reflection; direction mutated
    MISSED = "missed"  # no intersection; state unchanged


class OpticalIntersector:
    """Helper class for common optical intersection math."""

    @staticmethod
    def intersect_sphere(
        origin_x: float,
        origin_y: float,
        origin_z: float,
        dir_x: float,
        dir_y: float,
        dir_z: float,
        center_x: float,
        center_y: float,
        center_z: float,
        radius: float,
    ) -> Optional[Tuple[float, float]]:
        """
        Intersect a ray with a sphere.

        Returns:
            (t1, t2) parametric distances or None if no intersection.
        """
        oc_x = origin_x - center_x
        oc_y = origin_y - center_y
        oc_z = origin_z - center_z

        a = dir_x**2 + dir_y**2 + dir_z**2
        b = 2.0 * (oc_x * dir_x + oc_y * dir_y + oc_z * dir_z)
        c = oc_x**2 + oc_y**2 + oc_z**2 - radius**2

        discriminant = b * b - 4 * a * c
        if discriminant < -EPSILON:
            return None

        discriminant = max(0, discriminant)
        sqrt_disc = math.sqrt(discriminant)
        t1 = (-b - sqrt_disc) / (2 * a)
        t2 = (-b + sqrt_disc) / (2 * a)

        return (t1, t2)

    @staticmethod
    def apply_snell(
        incident_dir: Tuple[float, float, float],
        normal: Tuple[float, float, float],
        n1: float,
        n2: float,
    ) -> Optional[Tuple[float, float, float, bool]]:
        """
        Apply Snell's law in 3D.
        Returns (refracted_dir_x, refracted_dir_y, refracted_dir_z, is_tir).
        """
        ix, iy, iz = incident_dir
        nx, ny, nz = normal

        cos_i = -(ix * nx + iy * ny + iz * nz)
        enx, eny, enz = nx, ny, nz

        if cos_i < 0:
            cos_i = -cos_i
            enx, eny, enz = -nx, -ny, -nz

        ratio = n1 / n2
        sin2_t = ratio**2 * (1.0 - cos_i**2)

        if sin2_t > 1.0:
            dot = ix * enx + iy * eny + iz * enz
            rx = ix - 2 * dot * enx
            ry = iy - 2 * dot * eny
            rz = iz - 2 * dot * enz
            return (rx, ry, rz, True)

        cos_t = math.sqrt(1.0 - sin2_t)
        factor = ratio * cos_i - cos_t
        rx = ratio * ix + factor * enx
        ry = ratio * iy + factor * eny
        rz = ratio * iz + factor * enz

        mag = math.sqrt(rx**2 + ry**2 + rz**2)
        return (rx / mag, ry / mag, rz / mag, False)


class Ray:
    """
    Represents a light ray with position and direction.

    Attributes:
        x: X position (mm)
        y: Y position (mm) - height from optical axis
        angle: Angle in radians (from horizontal, positive = upward)
        wavelength: Wavelength in mm (default 0.000550 = 550nm green)
        n: Current refractive index the ray is traveling through
        path: List of (x, y) points along the ray path
    """

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        angle_rad: float = 0.0,
        wavelength_mm: float = WAVELENGTH_GREEN * NM_TO_MM,
        n: float = REFRACTIVE_INDEX_AIR,
    ) -> None:
        self.x = x
        self.y = y
        self.angle_rad = angle_rad
        self.wavelength = wavelength_mm
        self.n = n
        self.path: List[Tuple[float, float]] = [(self.x, self.y)]
        self.terminated = False
        self.hit: bool = False

    @property
    def angle(self) -> float:
        """Alias for angle_rad for backward compatibility."""
        return self.angle_rad

    @angle.setter
    def angle(self, value: float) -> None:
        self.angle_rad = value

    @property
    def wavelength_mm(self) -> float:
        """Alias for wavelength for backward compatibility."""
        return self.wavelength

    @wavelength_mm.setter
    def wavelength_mm(self, value: float) -> None:
        self.wavelength = value

    def propagate(self, distance_mm: float) -> None:
        """Propagate ray in current direction"""
        self.x += distance_mm * math.cos(self.angle_rad)
        self.y += distance_mm * math.sin(self.angle_rad)
        self.path.append((self.x, self.y))

    def refract_or_reflect(
        self, n1: float, n2: float, surface_normal_angle: float = 0.0
    ) -> RefractionResult:
        """
        Apply Snell's law at an interface.

        Args:
            n1: Refractive index of medium ray is coming from.
            n2: Refractive index of medium ray is entering.
            surface_normal_angle: Angle of surface normal (radians).

        Returns:
            REFRACTED  — transmitted; self.n updated to n2.
            REFLECTED  — total internal reflection; self.angle_rad updated.
            MISSED     — no valid solution; state unchanged.
        """
        incident_dir = (math.cos(self.angle_rad), math.sin(self.angle_rad), 0.0)
        normal = (math.cos(surface_normal_angle), math.sin(surface_normal_angle), 0.0)

        result = OpticalIntersector.apply_snell(incident_dir, normal, n1, n2)
        if result is None:
            return RefractionResult.MISSED

        rx, ry, _, is_tir = result
        self.angle_rad = math.atan2(ry, rx)

        if is_tir:
            return RefractionResult.REFLECTED

        self.n = n2
        return RefractionResult.REFRACTED


class Ray3D:
    """
    Represents a light ray in 3D space with optional polarization.
    """

    def __init__(
        self,
        origin: Vector3,
        direction: Vector3,
        wavelength: float = WAVELENGTH_GREEN * NM_TO_MM,
        intensity: float = 1.0,
        n: float = REFRACTIVE_INDEX_AIR,
        polarization_vector: Optional[Any] = None,
    ) -> None:
        self.origin = origin
        self.direction = direction.normalize()
        self.wavelength = wavelength
        self.intensity = intensity
        self.n = n
        self.path: List[Vector3] = [origin]
        self.terminated = False
        self.optical_path_length: float = 0.0

        self.polarization_vector = polarization_vector
        if self.polarization_vector is not None and HAS_POLARIZATION and np is not None:
            if not isinstance(self.polarization_vector, np.ndarray):
                self.polarization_vector = np.array(self.polarization_vector, dtype=complex)

    def propagate(self, distance: float) -> None:
        """Propagate ray in current direction"""
        self.origin = self.origin + self.direction * distance
        self.path.append(self.origin)
        self.optical_path_length += distance * self.n

    def _compute_fresnel_reflectance(
        self, n1: float, n2: float, cos_i: float, cos_t: float
    ) -> float:
        """Calculate Fresnel reflectance for unpolarized light."""
        if n1 == n2:
            return 0.0

        rs_den = n1 * cos_i + n2 * cos_t
        if rs_den == 0:
            return 1.0
        rs = ((n1 * cos_i - n2 * cos_t) / rs_den) ** 2

        rp_den = n1 * cos_t + n2 * cos_i
        if rp_den == 0:
            return 1.0
        rp = ((n1 * cos_t - n2 * cos_i) / rp_den) ** 2

        return 0.5 * (rs + rp)

    def _update_polarization(
        self,
        normal: Vector3,
        n1: float,
        n2: float,
        new_direction: Vector3,
        interaction: str,
    ) -> None:
        """
        Update polarization vector based on interaction (reflect/refract).
        """
        if (
            self.polarization_vector is None
            or not HAS_POLARIZATION
            or np is None
            or PolarizationCalculator is None
        ):
            return

        k_inc = self.direction
        n = normal

        s_vec = k_inc.cross(n)
        s_mag = s_vec.magnitude()

        if s_mag < 1e-6:
            if abs(k_inc.x) < 0.9:
                arb = vec3(1, 0, 0)
            else:
                arb = vec3(0, 1, 0)
            s_vec = k_inc.cross(arb).normalize()
        else:
            s_vec = s_vec.normalize()

        p_inc = s_vec.cross(k_inc).normalize()

        k_out = new_direction
        p_out = s_vec.cross(k_out).normalize()

        E = self.polarization_vector
        s_np = np.array([s_vec.x, s_vec.y, s_vec.z])
        p_inc_np = np.array([p_inc.x, p_inc.y, p_inc.z])
        p_out_np = np.array([p_out.x, p_out.y, p_out.z])

        E_s = np.dot(E, s_np)
        E_p = np.dot(E, p_inc_np)

        cos_i = abs(k_inc.dot(n))
        angle_deg = math.degrees(math.acos(min(1.0, cos_i)))

        calc = PolarizationCalculator()
        coeffs = calc.fresnel_coefficients(n1, n2, angle_deg)

        if interaction == "reflect":
            r_s = coeffs["r_s"]
            r_p = coeffs["r_p"]

            E_new = r_s * E_s * s_np + r_p * E_p * p_out_np

            R_s = np.abs(r_s) ** 2
            R_p = np.abs(r_p) ** 2

            P_total_old = np.abs(E_s) ** 2 + np.abs(E_p) ** 2
            if P_total_old > 1e-9:
                reflectance_factor = (R_s * np.abs(E_s) ** 2 + R_p * np.abs(E_p) ** 2) / P_total_old
                self.intensity *= reflectance_factor
            else:
                self.intensity = 0.0

            self.polarization_vector = E_new

        elif interaction == "refract":
            t_s = coeffs["t_s"]
            t_p = coeffs["t_p"]

            E_new = t_s * E_s * s_np + t_p * E_p * p_out_np

            if coeffs["total_internal_reflection"]:
                self.intensity = 0.0
                self.polarization_vector = np.zeros(3, dtype=complex)
                return

            theta1_rad = math.radians(angle_deg)
            theta2_rad = math.radians(float(coeffs["theta_transmitted_deg"].real))

            if n1 * math.cos(theta1_rad) > 1e-9:
                geo_factor = (n2 * math.cos(theta2_rad)) / (n1 * math.cos(theta1_rad))
            else:
                geo_factor = 0

            T_s = geo_factor * np.abs(t_s) ** 2
            T_p = geo_factor * np.abs(t_p) ** 2

            P_total_old = np.abs(E_s) ** 2 + np.abs(E_p) ** 2
            if P_total_old > 1e-9:
                transmittance_factor = (
                    T_s * np.abs(E_s) ** 2 + T_p * np.abs(E_p) ** 2
                ) / P_total_old
                self.intensity *= transmittance_factor
            else:
                self.intensity = 0.0

            self.polarization_vector = E_new

    def reflect(
        self, normal: Vector3, n1: Optional[float] = None, n2: Optional[float] = None
    ) -> None:
        """
        Reflect ray off a surface normal.
        """
        old_direction = self.direction
        dot = self.direction.dot(normal)

        new_direction = self.direction - normal * (2 * dot)
        new_direction = new_direction.normalize()
        self.direction = new_direction

        if n1 is not None and n2 is not None:
            if self.polarization_vector is not None and HAS_POLARIZATION:
                temp_ray_dir = self.direction
                self.direction = old_direction
                self._update_polarization(normal, n1, n2, new_direction, "reflect")
                self.direction = temp_ray_dir
                return

            cos_i = abs(dot)
            ratio = n1 / n2
            sin2_t = ratio**2 * (1.0 - cos_i**2)

            if sin2_t > 1.0:
                R = 1.0
            else:
                cos_t = math.sqrt(1.0 - sin2_t)
                R = self._compute_fresnel_reflectance(n1, n2, cos_i, cos_t)

            self.intensity *= R

    def refract_or_reflect(self, n1: float, n2: float, normal: Vector3) -> RefractionResult:
        """Apply Snell's law at an interface using vector math."""
        if self.polarization_vector is not None and HAS_POLARIZATION:
            # Handle polarized refraction with Fresnel coefficients
            incident_dir = (self.direction.x, self.direction.y, self.direction.z)
            normal_tuple = (normal.x, normal.y, normal.z)
            result = OpticalIntersector.apply_snell(incident_dir, normal_tuple, n1, n2)
            if result is None:
                return RefractionResult.MISSED
            rx, ry, rz, is_tir = result
            new_direction = vec3(rx, ry, rz)
            if is_tir:
                # Total internal reflection - treat as reflection
                self._update_polarization(normal, n1, n2, new_direction, "reflect")
                self.direction = new_direction
                return RefractionResult.REFLECTED
            # Update polarization and intensity for transmission
            self._update_polarization(normal, n1, n2, new_direction, "refract")
            self.direction = new_direction
            self.n = n2
            return RefractionResult.REFRACTED

        incident_dir = (self.direction.x, self.direction.y, self.direction.z)
        normal_tuple = (normal.x, normal.y, normal.z)

        result = OpticalIntersector.apply_snell(incident_dir, normal_tuple, n1, n2)
        if result is None:
            return RefractionResult.MISSED

        rx, ry, rz, is_tir = result
        new_direction = vec3(rx, ry, rz)

        if is_tir:
            self.direction = new_direction
            return RefractionResult.REFLECTED

        cos_i = abs(self.direction.dot(normal))
        cos_t = abs(new_direction.dot(normal))
        R = self._compute_fresnel_reflectance(n1, n2, cos_i, cos_t)
        self.intensity *= 1.0 - R

        self.direction = new_direction
        self.n = n2
        return RefractionResult.REFRACTED
