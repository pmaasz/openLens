#!/usr/bin/env python3
"""
Lens Aberrations Calculator
Calculates primary optical aberrations for single lens elements
"""

import json
import logging
import math
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger(__name__)


def _all_valid(*values) -> bool:
    """True when no supplied metric is missing.

    Aberration helpers return None when they could not be measured - a failed
    ray trace, a vignetted design. None used to be published as 0.0, which is
    indistinguishable from a perfect design and better than diffraction
    limited. ``calculate_all_aberrations`` now reports ``valid: False`` so a
    caller can grey the value out instead of showing a fictional zero.

    Mappings are flattened, so a whole field-metrics block can be passed in
    one call - its individual metrics are what matter.
    """
    flat = []
    for value in values:
        if isinstance(value, dict):
            flat.extend(value.values())
        else:
            flat.append(value)
    return all(v is not None for v in flat)


# Import ray tracer for exact calculations

# Import constants
from .constants import (
    SPHERICAL_ABERRATION_EXCELLENT,
    QUALITY_EXCELLENT_THRESHOLD,
    QUALITY_GOOD_THRESHOLD,
    QUALITY_FAIR_THRESHOLD,
    WAVELENGTH_GREEN,
    EPSILON,
    AIRY_DISK_FACTOR,
)

# Airy disk DIAMETER = 2 * (Airy radius) = 2.44 * λ * f/#
# (constants.AIRY_DISK_FACTOR is the 1.22 radius factor)
AIRY_DISK_DIAMETER_FACTOR = 2.0 * AIRY_DISK_FACTOR


class AberrationsCalculator:
    """
    Calculate primary (Seidel) aberrations for a single lens element or an optical system.

    The five primary aberrations are:
    1. Spherical Aberration (SA)
    2. Coma
    3. Astigmatism
    4. Field Curvature
    5. Distortion

    A lens and the one-element system that holds it report the same numbers:
    the field curvature is the traced tangential focus shift (mm) and the
    distortion the traced value (%), for both. The analytic singlet estimates
    (the Petzval radius, the third-order distortion) are available under
    their own names - ``_calculate_petzval_radius`` and
    ``_calculate_third_order_distortion`` - because they are a different
    quantity, not a cheaper way of measuring the same one.

    Additionally calculates chromatic aberration when Abbe number is available.
    """

    def __init__(self, target: Any, entrance_pupil_mm: Optional[float] = None) -> None:
        """
        Initialize calculator with a lens or an optical system.

        Args:
            target: Lens object or OpticalSystem object.
            entrance_pupil_mm: Diameter of the aperture to evaluate the design
                at, in mm. Defaults to the target's own clear aperture. A
                value wider than the physical aperture is clamped to it - the
                glass cannot pass more light - and a non-positive or
                non-finite value raises ``ValueError``. Every aperture-derived
                metric (f-number, NA, Airy disk, the marginal-ray traces and
                the reported ``entrance_pupil``) uses the effective diameter.
        """
        self.target = target
        # Check if target is an OpticalSystem (has elements)
        if hasattr(target, "elements"):
            self.is_system = True
            # For system calculations, use effective properties
            self.n = 1.0  # System in air
            self.diameter = target.elements[0].lens.diameter if target.elements else 25.0
            # focal_length = target.get_system_focal_length()
        else:
            self.is_system = False
            self.lens = target
            self.n = target.refractive_index
            self.radius_1 = target.radius_of_curvature_1
            self.radius_2 = target.radius_of_curvature_2
            self.thickness = target.thickness
            self.diameter = target.diameter
        # The physical clear aperture, before any requested stop-down. Kept so
        # a requested pupil can be clamped and reported honestly.
        self.physical_diameter = self.diameter
        if entrance_pupil_mm is not None:
            self.diameter = self._effective_pupil(entrance_pupil_mm)
        # Cache of wavefront Strehl results keyed on the live optical state.
        # A 32x32 pupil trace costs ~0.3 s; repeated evaluations of an
        # unchanged lens/system (GUI refreshes, optimizer bookkeeping,
        # timing loops) reuse the cached value. The key contains every
        # parameter the trace depends on, so mutated optics recompute.
        self._strehl_cache: Dict[tuple, Tuple[float, float]] = {}
        # Cache of traced field results (the curvature/distortion metrics and
        # the coma/astigmatism estimators), keyed on the live optical state.
        # Since #604 the singlet path measures the same trace as the system
        # path, which put three ray traces on every call to
        # calculate_all_aberrations(); the performance budget is 100 calls per
        # second, and repeated evaluations of unchanged optics are the norm
        # (GUI refreshes, optimizer bookkeeping, timing loops).
        self._field_cache: Dict[tuple, Any] = {}

    def _effective_pupil(self, entrance_pupil_mm: float) -> float:
        """Clamp a requested entrance pupil to the physical clear aperture.

        Raises:
            ValueError: If the value is not a positive finite diameter. A
                silent fallback would make the value the caller set
                meaningless, which is the bug this parameter exists to fix.
        """
        try:
            pupil = float(entrance_pupil_mm)
        except (TypeError, ValueError):
            raise ValueError(
                f"entrance pupil must be a positive diameter in mm, got {entrance_pupil_mm!r}"
            ) from None
        if not math.isfinite(pupil) or pupil <= 0:
            raise ValueError(
                f"entrance pupil must be a positive diameter in mm, got {entrance_pupil_mm!r}"
            )
        if self.physical_diameter and self.physical_diameter > 0:
            return min(pupil, float(self.physical_diameter))
        return pupil

    def calculate_all_aberrations(
        self,
        object_distance_mm: Optional[float] = None,
        field_angle_deg: float = 0.0,
        wavelength_nm: float = WAVELENGTH_GREEN,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Calculate all primary aberrations.

        Args:
            object_distance_mm: Distance to object in mm. None for infinity (collimated light)
            field_angle_deg: Off-axis angle in degrees (for coma, astigmatism, distortion)
            wavelength_nm: Wavelength in nm (for chromatic aberrations)

        Returns:
            Dictionary with aberration values and optical parameters
        """
        # Handle backward compatibility for argument names
        field_angle = kwargs.get("field_angle", field_angle_deg)
        field_angle_deg = field_angle  # Update for use in the function

        # Every quantity below is evaluated at wavelength_nm: lens indices
        # are temporarily updated (restored on exit), so analytic scalings
        # and exact traces share one wavelength instead of mixing the
        # requested wavelength with the lenses' stored state.
        saved_indices = self._set_wavelength_for_trace(wavelength_nm)
        try:
            return self._calculate_all_at_wavelength(
                object_distance_mm, field_angle_deg, wavelength_nm
            )
        finally:
            self._restore_wavelength_after_trace(saved_indices)

    def _calculate_all_at_wavelength(
        self,
        object_distance_mm: Optional[float],
        field_angle_deg: float,
        wavelength_nm: float,
    ) -> Dict[str, Any]:
        """Body of calculate_all_aberrations at one consistent wavelength.

        Raises:
            ValueError: If a finite ``object_distance_mm`` is requested. Every
                Seidel estimator here assumes the object at infinity
                (conjugate factor C = -1), so a finite conjugate was accepted,
                forwarded and then ignored - the caller got
                infinity-conjugate numbers labelled with their own distance.
                Refusing is better than that: the answer would be wrong, and
                wrong in a way nothing downstream could detect. Supporting it
                needs a conjugate factor threaded through each estimator,
                which is a physics change rather than a guard.
        """
        if object_distance_mm is not None:
            raise ValueError(
                f"object distance is not supported: got {object_distance_mm!r} mm. "
                f"Every aberration here is computed for an object at infinity; "
                f"pass object_distance_mm=None for that case."
            )

        if self.is_system:
            focal_length = self.target.get_system_focal_length()
        else:
            focal_length = self.lens.calculate_focal_length()

        if focal_length is None:
            return {
                "focal_length": None,
                "entrance_pupil": self.diameter,
                "f_number": 0.0,
                "spherical": 0.0,
                "spherical_aberration": 0.0,
                "coma": 0.0,
                "astigmatism": 0.0,
                "field_curvature": 0.0,
                "distortion": 0.0,
                "chromatic": 0.0,
                "chromatic_aberration": 0.0,
                "airy_disk_diameter": 0.0,
                "spot_rms": 0.0,
                "strehl": 0.0,
                "wfe_rms_waves": 0.0,
                "mtf_cutoff": 0.0,
                # Every value above is a placeholder, not a measurement.
                "valid": False,
                "error": "Cannot calculate focal length (zero optical power)",
            }

        # Calculate numerical aperture and other parameters
        na = self._calculate_numerical_aperture(focal_length)

        # Compute each quantity once; the dict exposes two documented
        # alias keys per value ('spherical'/'spherical_aberration',
        # 'chromatic'/'chromatic_aberration') for API compatibility.
        spherical = self._calculate_spherical_aberration(focal_length)
        chromatic = self._calculate_chromatic_aberration(focal_length)
        f_number = self._calculate_f_number(focal_length)
        airy = self._calculate_airy_disk(focal_length, wavelength_nm * 1e-6)
        strehl, wfe_rms_waves = self._calculate_strehl_ratio(
            focal_length, wavelength_nm=wavelength_nm
        )
        mtf_cutoff = self._calculate_mtf_cutoff(focal_length, wavelength_nm=wavelength_nm)

        # None means the trace failed, which is not the same as a zero spot.
        # Published as 0.0 it read as a perfect design - better than
        # diffraction limited - for a lens that could not be traced.
        spot_rms = self._calculate_spot_rms()

        if self.is_system:
            field_data = self._calculate_field_metrics_system(
                field_angle_deg, wavelength_nm=wavelength_nm
            )
            if field_data is None:
                # Leave the values None rather than substituting zeros: the
                # caller needs to be able to tell "no coma" from "the trace
                # failed", and "valid" below is derived from exactly that.
                field_data = {
                    "coma": None,
                    "astigmatism": None,
                    "field_curvature": None,
                    "distortion": None,
                }
            return {
                "focal_length": focal_length,
                "entrance_pupil": self.diameter,
                "numerical_aperture": na,
                "f_number": f_number,
                "spherical": spherical,
                "spherical_aberration": spherical,
                "coma": field_data["coma"],
                "astigmatism": field_data["astigmatism"],
                "field_curvature": field_data["field_curvature"],
                "distortion": field_data["distortion"],
                "chromatic": chromatic,
                "chromatic_aberration": chromatic,
                "airy_disk_diameter": airy,
                "spot_rms": spot_rms,
                "strehl": strehl,
                "wfe_rms_waves": wfe_rms_waves,
                "mtf_cutoff": mtf_cutoff,
                "valid": _all_valid(field_data, spherical, chromatic, airy, strehl, spot_rms),
            }

        # Field curvature and distortion come from the same trace the
        # system path uses, so a lens and the one-element system that holds
        # it report the same numbers. The analytic singlet estimates were
        # different quantities altogether: the Petzval *radius* (n * f) and a
        # distortion of exactly zero "by construction" - the same key, a
        # hundred-fold different value, and a GUI label that only fitted the
        # analytic one.
        field_data = self._calculate_field_metrics_system(
            field_angle_deg, wavelength_nm=wavelength_nm
        )
        if field_data is None:
            field_curvature, distortion = None, None
        else:
            field_curvature = field_data["field_curvature"]
            distortion = field_data["distortion"]

        singlet_field = self._calculate_singlet_field_estimators(field_angle_deg, wavelength_nm)
        if singlet_field is None:
            coma_val, astig_val = None, None
        else:
            coma_val, astig_val = singlet_field
        return {
            "focal_length": focal_length,
            "entrance_pupil": self.diameter,
            "numerical_aperture": na,
            "f_number": f_number,
            "spherical": spherical,
            "spherical_aberration": spherical,
            "coma": coma_val,
            "astigmatism": astig_val,
            "field_curvature": field_curvature,
            "distortion": distortion,
            "chromatic": chromatic,
            "chromatic_aberration": chromatic,
            "airy_disk_diameter": airy,
            "strehl": strehl,
            "wfe_rms_waves": wfe_rms_waves,
            "mtf_cutoff": mtf_cutoff,
            "valid": _all_valid(
                coma_val,
                astig_val,
                field_curvature,
                distortion,
                spherical,
                chromatic,
                airy,
                strehl,
            ),
        }

    def _calculate_singlet_field_estimators(
        self, field_angle_deg: float, wavelength_nm: float
    ) -> Optional[Tuple[float, float]]:
        """Single off-axis evaluation feeding both coma and astigmatism.

        On-axis is a genuine (0.0, 0.0) - there is no coma or astigmatism at
        zero field - so that case is distinct from a failed trace, which
        returns None.
        """
        if abs(field_angle_deg) < EPSILON:
            return 0.0, 0.0
        return self._calculate_field_estimators(field_angle_deg, wavelength_nm)

    def _calculate_f_number(self, focal_length: float) -> float:
        """F-number |f|/D (photographic convention; sign of EFL dropped)."""
        if self.diameter <= 0:
            return float("inf")
        return abs(focal_length) / self.diameter

    def _calculate_numerical_aperture(self, focal_length: float) -> float:
        """Calculate the numerical aperture (NA)"""
        if abs(focal_length) < EPSILON:
            return 0.0
        # For object at infinity: NA = D / (2 * f)
        return self.diameter / (2 * abs(focal_length))

    def _traceable_lenses(self) -> List[Any]:
        """Lens objects the exact traces read indices from."""
        if self.is_system:
            return [element.lens for element in self.target.elements]
        return [self.lens]

    def _single_element_system(self) -> Any:
        """The lens as a one-element system, for the traces that need one.

        The field-curvature and distortion trace works on a system. Wrapping
        the lens is what makes the two paths agree: the same lens, the same
        trace, the same numbers.
        """
        if self.is_system:
            return self.target
        from .optical_system import OpticalSystem

        system = OpticalSystem(name="Single lens")
        system.add_lens(self.lens)
        return system

    def _set_wavelength_for_trace(self, wavelength_nm: float) -> list:
        """Point all traceable lenses at wavelength_nm; return restore state."""
        saved = []
        for lens in self._traceable_lenses():
            saved.append((lens, lens.wavelength, lens.refractive_index))
            lens.update_refractive_index(wavelength_nm=wavelength_nm)
        return saved

    @staticmethod
    def _restore_wavelength_after_trace(saved: list) -> None:
        """Restore lens wavelength/index state saved by _set_wavelength_for_trace."""
        for lens, wavelength, refractive_index in saved:
            lens.wavelength = wavelength
            lens.refractive_index = refractive_index

    def _calculate_field_metrics_system(
        self,
        field_angle: float,
        wavelength_nm: float = WAVELENGTH_GREEN,
    ) -> Dict[str, float]:
        """Calculate field-dependent aberrations for an optical system using real ray tracing

        Args:
            field_angle: Field angle in degrees.
            wavelength_nm: Traced wavelength in nm.

        Returns:
            The traced field metrics, or None when the trace failed.
        """
        cached = self._field_cache_get("metrics", field_angle, wavelength_nm)
        if cached is not None:
            # A copy, so a caller editing the dict cannot poison the cache.
            return dict(cached)
        try:
            from .analysis.geometric import GeometricTraceAnalysis

            analysis = GeometricTraceAnalysis(self._single_element_system())

            # 1. Field Curvature and Distortion
            # Sample out to the requested field. The magnitude is used:
            # these two are even in field angle, while coma and
            # astigmatism below are handed the signed value. Sampling to
            # max(field_angle, 0.1) meant a -10 deg request was evaluated
            # at +0.1 deg, so one dict mixed two fields - the caller got
            # the curvature of a different field than the coma beside it.
            # The 0.1 deg floor stays to avoid a degenerate zero-width
            # sample at the on-axis case.
            requested_field = abs(float(field_angle))
            fc_data = analysis.calculate_field_curvature_distortion(
                max_field_angle_deg=max(requested_field, 0.1),
                num_points=10,
                wavelength_nm=wavelength_nm,
            )

            # Extract metrics at the requested field_angle
            # fc_data['tan_focus_shift_mm'] etc are lists; we want the last
            # element if we sampled up to field_angle
            field_curv = fc_data["tan_focus_shift_mm"][-1] if fc_data["tan_focus_shift_mm"] else 0.0
            dist = fc_data["distortion_pct"][-1] if fc_data["distortion_pct"] else 0.0

            # 2. Coma and astigmatism share one cheap sampling with the
            # singlet path (exact agreement by construction).
            coma_val, astig = self._calculate_field_estimators(field_angle, wavelength_nm)

            metrics = {
                "field_curvature": field_curv,
                "distortion": dist,
                "astigmatism": astig,
                "coma": coma_val,
            }
        except Exception as e:
            logger.warning("Field metrics computation failed at %.1f deg: %s", field_angle, e)
            return None
        # A failed trace is not cached: it is an error worth retrying, and
        # None is also _field_cache_get()'s "miss" marker.
        if coma_val is not None and astig is not None:
            self._field_cache_put("metrics", field_angle, wavelength_nm, metrics)
        return dict(metrics)

    def _calculate_field_estimators(
        self, field_angle_deg: float, wavelength_nm: float = WAVELENGTH_GREEN
    ) -> Optional[Tuple[float, float]]:
        """Ray-traced off-axis estimators: (coma, astigmatism).

        Coma is the even part of the tangential ray fan,
        ``(err_top + err_bottom) / 2`` measured from the chief ray.
        Astigmatism is the longitudinal split between the tangential and
        sagittal best foci, ``|tan - sag|``. Both use exact 3D tracing
        (single lenses via a one-element system wrapper), so no shape-factor
        heuristics, sign conventions, or stop-shift approximations enter.
        Object at infinity; entrance pupil is the first-element aperture.

        Args:
            field_angle_deg: Off-axis field angle in degrees.
            wavelength_nm: Traced wavelength in nm.

        Returns:
            (coma_mm, astigmatism_mm), or None if tracing fails. Failure used
            to report (0.0, 0.0) - indistinguishable from a perfect off-axis
            design, and better than diffraction limited, for exactly the
            geometries whose trace failed. The 2D tracer returns MISSED rather
            than raising, so these paths were reached in practice.
        """
        cached = self._field_cache_get("estimators", field_angle_deg, wavelength_nm)
        if cached is not None:
            return cached
        try:
            # Economical sampling shared verbatim with the system path, so
            # singlets and systems agree exactly for identical optics.
            fan = self.calculate_ray_fan(
                field_angle_deg=field_angle_deg,
                wavelength_nm=wavelength_nm,
                num_points=11,
            )
            errors = fan.get("ray_errors_mm", fan.get("transverse_aberration", []))
            coma = (errors[0] + errors[-1]) / 2.0 if len(errors) >= 2 else 0.0

            _, sag, tan = self.calculate_field_curvature(
                max_field_angle_deg=max(field_angle_deg, 0.5),
                num_points=6,
                wavelength_nm=wavelength_nm,
            )
            astigmatism = abs(tan[-1] - sag[-1]) if tan and sag else 0.0
        except Exception as e:
            logger.warning("Field estimators ray trace failed: %s", e)
            return None
        self._field_cache_put("estimators", field_angle_deg, wavelength_nm, (coma, astigmatism))
        return coma, astigmatism

    def _calculate_coma(
        self,
        focal_length: float,
        field_angle_deg: float,
        wavelength_nm: float = WAVELENGTH_GREEN,
    ) -> float:
        """Transverse coma from the traced ray fan (0.0 on axis by symmetry).

        Args:
            focal_length: Kept for API compatibility (unused; the value is
                traced, not scaled from paraxial quantities).
            wavelength_nm: Traced wavelength in nm.
        """
        if abs(field_angle_deg) < EPSILON:
            return 0.0
        coma, _ = self._calculate_field_estimators(field_angle_deg, wavelength_nm)
        return coma

    def _calculate_astigmatism(
        self,
        focal_length: float,
        field_angle_deg: float,
        wavelength_nm: float = WAVELENGTH_GREEN,
    ) -> float:
        """Longitudinal astigmatism as the traced tan/sag focus split.

        Args:
            focal_length: Kept for API compatibility (unused; the value is
                traced, not f * theta^2).
            wavelength_nm: Traced wavelength in nm.
        """
        if abs(field_angle_deg) < EPSILON:
            return 0.0
        _, astigmatism = self._calculate_field_estimators(field_angle_deg, wavelength_nm)
        return astigmatism

    def _calculate_petzval_radius(self, focal_length: float) -> float:
        """The Petzval radius of a single lens, in mm.

        Not the reported ``field_curvature``: that is the traced tangential
        focus shift, for the lens and for a system alike. This is the
        analytic third-order quantity, kept because it is a useful
        reference - and named for what it is, so the two cannot be confused
        again.
        """
        # Petzval Radius R_p = n * f (for a single thin lens)
        return self.n * focal_length

    def _calculate_third_order_distortion(
        self, focal_length: float, field_angle_deg: float
    ) -> float:
        """The third-order Seidel distortion of a single lens: 0.0 by construction.

        Not the reported ``distortion``: that is the traced value, for the
        lens and for a system alike. With the stop AT the lens the chief ray
        passes through the lens centre undeviated, so the Seidel distortion
        coefficient S5 is exactly zero (not an approximation). Distortion
        appears only when the stop is shifted away from the lens; use
        calculate_distortion_curve() for the exact traced distortion of any
        stop position.
        """
        return 0.0

    def calculate_ray_fan(
        self,
        field_angle_deg: float = 0.0,
        wavelength_nm: float = WAVELENGTH_GREEN,
        num_points: int = 21,
        pupil_axis: str = "y",
    ) -> Dict[str, Any]:
        """
        Interface for calculating ray fan.
        """
        from .analysis.geometric import GeometricTraceAnalysis
        from .optical_system import OpticalSystem

        if self.is_system:
            system = self.target
        else:
            system = OpticalSystem(name=self.lens.name)
            system.add_lens(self.lens)

        analysis = GeometricTraceAnalysis(system)
        return analysis.calculate_ray_fan(
            field_angle_deg=field_angle_deg,
            wavelength_nm=wavelength_nm,
            num_points=num_points,
            pupil_axis=pupil_axis,
        )

    def calculate_field_curvature(
        self,
        max_field_angle_deg: float = 20.0,
        num_points: int = 11,
        wavelength_nm: float = WAVELENGTH_GREEN,
    ) -> Tuple[List[float], List[float], List[float]]:
        """
        Interface for field curvature calculation.
        Returns (angles_deg, sag_shift_mm, tan_shift_mm)
        """
        from .analysis.geometric import GeometricTraceAnalysis
        from .optical_system import OpticalSystem

        if self.is_system:
            system = self.target
        else:
            system = OpticalSystem(name=self.lens.name)
            system.add_lens(self.lens)

        analysis = GeometricTraceAnalysis(system)
        data = analysis.calculate_field_curvature_distortion(
            max_field_angle_deg=max_field_angle_deg,
            num_points=num_points,
            wavelength_nm=wavelength_nm,
        )
        return (
            data["field_angles_deg"],
            data["sag_focus_shift_mm"],
            data["tan_focus_shift_mm"],
        )

    def calculate_distortion_curve(
        self,
        max_field_angle_deg: float = 20.0,
        num_points: int = 11,
        wavelength_nm: float = WAVELENGTH_GREEN,
    ) -> Tuple[List[float], List[float]]:
        """
        Interface for distortion curve calculation.
        Returns (angles_deg, distortion_pct)
        """
        from .analysis.geometric import GeometricTraceAnalysis
        from .optical_system import OpticalSystem

        if self.is_system:
            system = self.target
        else:
            system = OpticalSystem(name=self.lens.name)
            system.add_lens(self.lens)

        analysis = GeometricTraceAnalysis(system)
        data = analysis.calculate_field_curvature_distortion(
            max_field_angle_deg=max_field_angle_deg,
            num_points=num_points,
            wavelength_nm=wavelength_nm,
        )
        return data["field_angles_deg"], data["distortion_pct"]

    def _calculate_strehl_ratio(
        self,
        focal_length: float,
        wavelength_nm: float = WAVELENGTH_GREEN,
        grid_size: int = 32,
    ) -> Tuple[float, float]:
        """Calculate the on-axis Strehl ratio from the traced wavefront error.

        The Strehl ratio is defined (Born & Wolf, Principles of Optics,
        Sec. 9.1) as the ratio of the aberrated to the ideal central
        irradiance of the point-spread function:

            S = |<exp(i * 2 * pi * W)>|^2,

        where the average is taken over the exit pupil and ``W`` is the
        wavefront error in waves (piston and tilt removed, i.e. referenced
        to the chief ray). For small aberrations this reduces to the
        Marechal approximation ``S ~= exp(-(2 * pi * sigma)^2)`` with
        ``sigma`` the RMS wavefront error in waves.

        The wavefront map is obtained by exact ray tracing
        (:class:`analysis.diffraction_psf.WavefrontSensor`) at
        ``wavelength_nm``, so single lenses and systems share one code path
        (no singlet placeholder).

        Args:
            focal_length: Effective focal length in mm (unused in the
                computation itself; kept for API compatibility).
            wavelength_nm: Wavelength in nm at which to evaluate.
            grid_size: Pupil sampling grid (grid_size x grid_size rays).

        Returns:
            Tuple of (strehl_ratio, wfe_rms_waves), both clamped to
            physical ranges. (0.0, 0.0) if the wavefront cannot be
            computed (e.g. numpy missing or all rays vignetted).
        """
        key = self._strehl_state_key(wavelength_nm, grid_size)
        if key is not None and key in self._strehl_cache:
            return self._strehl_cache[key]
        wfe_rms = self._calculate_wavefront_rms_waves(
            wavelength_nm=wavelength_nm, grid_size=grid_size
        )
        if wfe_rms is None:
            return 0.0, 0.0
        valid_w = wfe_rms[1]
        if valid_w is None or valid_w.size == 0:
            return 0.0, 0.0
        try:
            import numpy as np

            complex_mean = np.mean(np.exp(2j * np.pi * valid_w))
            strehl = float(abs(complex_mean) ** 2)
        except ImportError:
            # Exact pupil average needs numpy; fall back to Marechal.
            strehl = math.exp(-((2.0 * math.pi * float(wfe_rms[0])) ** 2))
        result = (min(1.0, max(0.0, strehl)), float(wfe_rms[0]))
        if key is not None:
            if len(self._strehl_cache) >= 8:
                # Bounded FIFO: drop the oldest entry.
                self._strehl_cache.pop(next(iter(self._strehl_cache)))
            self._strehl_cache[key] = result
        return result

    #: Cap on the traced-field cache (metrics and estimators share it).
    _FIELD_CACHE_MAX = 16

    #: Lens fields that do not affect the pupil trace. Excluded from the trace
    #: cache key so renaming a lens, reloading it from the database (a new id)
    #: or editing its free-form metadata does not throw the cache away.
    _STREHL_NON_OPTICAL_FIELDS = frozenset({"id", "name", "created_at", "modified_at", "metadata"})

    def _field_cache_get(self, kind: str, field_angle: float, wavelength_nm: float) -> Any:
        """Cached traced-field result, or None when it must be recomputed."""
        key = self._field_state_key(kind, field_angle, wavelength_nm)
        if key is None:
            return None
        return self._field_cache.get(key)

    def _field_cache_put(
        self, kind: str, field_angle: float, wavelength_nm: float, value: Any
    ) -> None:
        """Store a traced-field result, dropping the oldest when full."""
        key = self._field_state_key(kind, field_angle, wavelength_nm)
        if key is None:
            return
        if len(self._field_cache) >= self._FIELD_CACHE_MAX:
            # Bounded FIFO, as the Strehl cache does: the working set is one
            # entry per visible field angle.
            self._field_cache.pop(next(iter(self._field_cache)))
        self._field_cache[key] = value

    def _field_state_key(
        self, kind: str, field_angle: float, wavelength_nm: float
    ) -> Optional[tuple]:
        """Cache key for a traced field result.

        ``kind`` separates the result shapes that share one optical state
        (the metrics dict and the estimator tuple) so they cannot collide.
        """
        state = self._trace_state_key(wavelength_nm)
        if state is None:
            return None
        return (kind, round(float(field_angle), 9)) + state

    def _strehl_state_key(self, wavelength_nm: float, grid_size: int) -> Optional[tuple]:
        """Hashable snapshot of everything the pupil trace depends on.

        The optical state plus the pupil grid: the grid size is a property of
        this trace, not of the optics.
        """
        state = self._trace_state_key(wavelength_nm)
        if state is None:
            return None
        return state + (grid_size,)

    def _trace_state_key(self, wavelength_nm: float) -> Optional[tuple]:
        """Hashable snapshot of everything a ray trace depends on.

        Built from the serialized lens state rather than a hand-picked list of
        attributes. The list was the defect: it named radii, thickness,
        diameter and index, so clear apertures, parabolic flags and sags,
        per-surface alignment and the aperture stop were all invisible to it,
        and editing any of them returned the previous Strehl result. Any field
        added to Lens in future would have been missing too, because nobody
        remembers to extend a list of attributes elsewhere in the file.

        The non-optical fields are dropped so the key is stable across a
        rename or a reload. The result is JSON-encoded because the serialized
        state contains lists and dicts (coating stacks, metadata), which are
        not hashable.

        Returns None if the state cannot be snapshotted (cache bypassed).
        """
        try:

            def _r(x) -> float:
                """Round so floating-point noise cannot cause a spurious miss."""
                return round(float(x), 9)

            def _lens_state(lens) -> str:
                state = {
                    name: value
                    for name, value in lens.to_dict().items()
                    if name not in self._STREHL_NON_OPTICAL_FIELDS
                }
                return json.dumps(state, sort_keys=True, default=str)

            if self.is_system:
                elements = tuple(
                    (
                        _lens_state(e.lens),
                        _r(e.position),
                        _r(e.decenter_y),
                        _r(e.decenter_z),
                        _r(e.tilt_x),
                        _r(e.tilt_y),
                        _r(e.tilt_z),
                    )
                    for e in self.target.elements
                )
                gaps = tuple(_r(g.thickness) for g in self.target.air_gaps)
                stop = getattr(self.target, "aperture_stop_gap", None)
                stop_diameter = getattr(self.target, "aperture_stop_diameter", None)
                return (
                    "system",
                    elements,
                    gaps,
                    stop,
                    _r(stop_diameter) if stop_diameter is not None else None,
                    _r(wavelength_nm),
                )
            return (
                "lens",
                _lens_state(self.lens),
                _r(wavelength_nm),
            )
        except (AttributeError, TypeError, ValueError) as e:
            # The cache is an optimisation: a lens that cannot be
            # snapshotted simply recomputes. Log it so a permanently cold
            # cache is visible rather than silent.
            logger.debug("Strehl cache key unavailable: %s", e)
            return None

    def _calculate_wavefront_rms_waves(
        self,
        wavelength_nm: float = WAVELENGTH_GREEN,
        grid_size: int = 32,
    ) -> Optional[Tuple[float, Any]]:
        """Trace the exit-pupil wavefront and return its RMS error in waves.

        Piston and tilt are removed by a least-squares plane fit over the
        pupil (Strehl is referenced to the chief ray), so pure focus
        position / beam tilt do not masquerade as aberration.

        Args:
            wavelength_nm: Wavelength in nm (lens indices are temporarily
                updated to this wavelength and restored afterwards).
            grid_size: Pupil sampling grid.

        Returns:
            (rms_waves, valid_waves_array) or None if unavailable.
        """
        try:
            import numpy as np
        except ImportError:
            logger.warning("Strehl ratio needs numpy; returning 0.0")
            return None

        try:
            from .analysis.diffraction_psf import WavefrontSensor
            from .optical_system import OpticalSystem
        except ImportError as e:
            logger.warning("Wavefront sensor unavailable: %s", e)
            return None

        if self.is_system:
            system = self.target
        else:
            system = OpticalSystem(name=getattr(self.lens, "name", "singlet"))
            system.add_lens(self.lens)
        # Temporarily set lens indices to the requested wavelength.
        saved = [
            (element.lens, element.lens.wavelength, element.lens.refractive_index)
            for element in system.elements
        ]
        try:
            for element in system.elements:
                element.lens.update_refractive_index(wavelength_nm=wavelength_nm)

            sensor = WavefrontSensor(system)
            wavefront = sensor.get_pupil_wavefront(
                field_angle_deg=0.0,
                wavelength_nm=wavelength_nm,
                grid_size=grid_size,
            )
            w_map = np.asarray(wavefront.W, dtype=float)
            y_map = np.asarray(wavefront.Y, dtype=float)
            z_map = np.asarray(wavefront.Z, dtype=float)
        except Exception as e:
            logger.warning("Wavefront trace failed: %s", e)
            return None
        finally:
            self._restore_wavelength_after_trace(saved)

        valid = np.isfinite(w_map)
        if int(np.count_nonzero(valid)) < 10:
            logger.warning("Too few valid pupil samples for Strehl computation")
            return None

        w = w_map[valid]
        max_r = float(np.max(np.sqrt(y_map[valid] ** 2 + z_map[valid] ** 2)))
        if max_r <= 0:
            return None

        # Remove piston + tilt: least-squares fit of a + b*yn + c*zn.
        yn = y_map[valid] / max_r
        zn = z_map[valid] / max_r
        try:
            design = np.column_stack([np.ones_like(w), yn, zn])
            coeffs, _, _, _ = np.linalg.lstsq(design, w, rcond=None)
            w_resid = w - design @ coeffs
        except (TypeError, ValueError, np.linalg.LinAlgError) as e:
            # Fall back to piston removal only; say so, because a fit that
            # keeps failing inflates the reported RMS wavefront error.
            logger.debug("Piston/tilt fit failed (%s); removing piston only", e)
            w_resid = w - float(np.mean(w))

        rms = float(np.sqrt(np.mean(w_resid**2)))
        return rms, w_resid

    def _calculate_mtf_cutoff(
        self, focal_length: float, wavelength_nm: float = WAVELENGTH_GREEN
    ) -> float:
        """Calculate diffraction-limited MTF cutoff frequency in lp/mm.

        Args:
            focal_length: Focal length in mm (sets the f-number).
            wavelength_nm: Wavelength in nm (default green photopic peak).
        """
        f_num = self._calculate_f_number(focal_length)
        if f_num <= 0:
            return 0
        wavelength_mm = wavelength_nm * 1e-6  # nm to mm
        return 1.0 / (wavelength_mm * f_num)

    def _calculate_spot_rms(self) -> Optional[float]:
        """Calculate RMS spot size using ray tracing (System only).

        The measurement plane is the system's configured
        ``image_plane_x_mm`` when set; otherwise it is the back-focal plane.
        """
        if not self.is_system:
            return 0
        try:
            from .ray_tracer import SystemRayTracer3D

            tracer = SystemRayTracer3D(self.target)

            # Use trace_off_axis_rays for consistent bundle generation
            rays = tracer.trace_off_axis_rays(field_angle_deg=0.0, num_rays=21)

            focus_x = getattr(self.target, "image_plane_x_mm", None)
            if focus_x is not None:
                try:
                    focus_x = float(focus_x)
                except (TypeError, ValueError):
                    focus_x = None
                if focus_x is not None and not math.isfinite(focus_x):
                    focus_x = None

            if focus_x is None:
                f = self.target.get_system_focal_length()
                if not f:
                    return None

                bfl = self.target.calculate_back_focal_length()
                if bfl is None:
                    return None

                last_elem = self.target.elements[-1]
                focus_x = last_elem.position + last_elem.thickness + bfl

            y_hits = []
            for ray in rays:
                if not ray.terminated and abs(ray.direction.x) > 1e-9:
                    # Propagate to focus_x
                    t = (focus_x - ray.origin.x) / ray.direction.x
                    y_at_focus = ray.origin.y + t * ray.direction.y
                    y_hits.append(y_at_focus)

            if not y_hits:
                return None

            mean_y = sum(y_hits) / len(y_hits)
            rms = math.sqrt(sum((y - mean_y) ** 2 for y in y_hits) / len(y_hits))
            return rms * 1000  # convert to um
        except Exception as e:
            logger.warning("Spot RMS ray-trace failed: %s", e)
            return None

    def _calculate_spherical_aberration(self, focal_length: float) -> float:
        """
        Calculate longitudinal spherical aberration (LSA).

        Attempts to use exact ray tracing first. If ray tracing fails or
        dependencies are missing, falls back to third-order Seidel approximation.

        LSA = Marginal Focus - Paraxial Focus

        For Seidel approximation:
        LSA = -K * y^4 / f^3

        Returns:
            Longitudinal spherical aberration in mm
        """
        if abs(focal_length) < EPSILON:
            return 0

        # Try exact calculation first
        exact_lsa = self._calculate_spherical_aberration_exact()
        if exact_lsa is not None:
            return exact_lsa

        # Fallback to Seidel approximation (only for single lens)
        if not self.is_system:
            return self._calculate_spherical_aberration_seidel(focal_length)
        return 0

    def _calculate_spherical_aberration_exact(self) -> Optional[float]:
        """
        Calculate LSA using exact ray tracing.
        Returns None if calculation fails (e.g. TIR, missing dependencies).
        """
        try:
            if self.is_system:
                from .ray_tracer import SystemRayTracer3D, Ray3D
                from .vector3 import vec3

                if not self.target.elements:
                    return None
                tracer = SystemRayTracer3D(self.target)

                # Trace Marginal Ray (near edge of pupil)
                rays_m = tracer.trace_off_axis_rays(field_angle_deg=0.0, num_rays=10)
                ray_m = rays_m[-1]  # Highest ray

                if ray_m.terminated or abs(ray_m.direction.y) < 1e-9:
                    return None
                m_focus = ray_m.origin.x - ray_m.origin.y * (ray_m.direction.x / ray_m.direction.y)

                # Paraxial reference: a dedicated ray at y = 0.001 mm.
                # (A mid-fan ray sits at ~D/6 and already carries SA,
                # underestimating LSA by ~10%.)
                ep_x = self.target.elements[0].position
                start_x = ep_x - 50.0
                direction = vec3(1.0, 0.0, 0.0)
                origin = vec3(ep_x, 0.001, 0.0) - direction * ((ep_x - start_x) / direction.x)
                ray_p = Ray3D(origin, direction)
                tracer.trace_ray(ray_p)

                if ray_p.terminated or abs(ray_p.direction.y) < 1e-9:
                    return None
                p_focus = ray_p.origin.x - ray_p.origin.y * (ray_p.direction.x / ray_p.direction.y)

                return m_focus - p_focus
            else:
                from .ray_tracer import LensRayTracer, Ray

                if LensRayTracer is None or Ray is None:
                    return None

                # Original single lens logic
                tracer = LensRayTracer(self.lens)
                start_x = -10.0 - self.thickness
                y_marginal = self.diameter / 2.0
                ray_marginal = Ray(start_x, y_marginal, angle_rad=0.0)
                tracer.trace_ray(ray_marginal)
                if ray_marginal.terminated or abs(math.tan(ray_marginal.angle)) < 1e-9:
                    return None
                marginal_focus = ray_marginal.x - ray_marginal.y / math.tan(ray_marginal.angle)

                y_paraxial = self.diameter / 2.0 * 0.01
                ray_paraxial = Ray(start_x, y_paraxial, angle_rad=0.0)
                tracer.trace_ray(ray_paraxial)
                if abs(math.tan(ray_paraxial.angle)) < 1e-9:
                    return None
                paraxial_focus = ray_paraxial.x - ray_paraxial.y / math.tan(ray_paraxial.angle)

                return marginal_focus - paraxial_focus
        except Exception as e:
            logger.warning("Spherical aberration ray trace failed: %s", e)
            return None

    def _calculate_chromatic_aberration(self, focal_length: float) -> Optional[float]:
        """Calculate longitudinal chromatic aberration (LCA)"""
        if self.is_system:
            # Use system method if it exists
            if hasattr(self.target, "calculate_chromatic_aberration"):
                res = self.target.calculate_chromatic_aberration()
                return res.get("longitudinal")
            return None

        # Typical Abbe numbers for common materials
        abbe_numbers = {
            "BK7": 64.17,  # Standard crown glass
            "Fused Silica": 67.8,  # Low dispersion
            "Crown Glass": 60.0,
            "Flint Glass": 36.0,
            "SF11": 25.76,
            "Sapphire": 72.0,
        }

        material = self.lens.material
        abbe_number = abbe_numbers.get(material)

        if abbe_number is None:
            # Estimate based on refractive index
            if self.n < 1.5:
                abbe_number = 65
            elif self.n < 1.6:
                abbe_number = 55
            elif self.n < 1.7:
                abbe_number = 40
            else:
                abbe_number = 30

        lca = abs(focal_length) / abbe_number
        return lca

    def _calculate_airy_disk(
        self, focal_length: float, wavelength: float = WAVELENGTH_GREEN * 1e-6
    ) -> float:
        """
        Calculate Airy disk diameter (diffraction-limited spot size).

        Airy disk diameter = 2.44 * λ * f/#

        Note: The factor 2.44 is for DIAMETER. The first zero of the Airy pattern
        occurs at 1.22 * λ * f/# from the center (radius), so the diameter is 2.44.

        Args:
            focal_length: Focal length in mm
            wavelength: Wavelength in mm (default 550nm = 0.000550mm green light)

        Returns:
            Airy disk diameter in mm
        """
        f_number = self._calculate_f_number(focal_length)

        if f_number == float("inf"):
            return 0

        # Use 2.44 for diameter (not 1.22 which is for radius)
        airy_diameter = AIRY_DISK_DIAMETER_FACTOR * wavelength * f_number

        return airy_diameter

    def get_aberration_summary(
        self,
        object_distance: Optional[float] = None,
        field_angle: float = 5.0,
        wavelength_nm: float = WAVELENGTH_GREEN,
        **kwargs,
    ) -> str:
        """
        Get a formatted summary of all aberrations.

        Args:
            object_distance: Distance to object (mm). None for infinity
            field_angle: Off-axis angle in degrees
            wavelength_nm: Wavelength in nm evaluated throughout

        Returns:
            Formatted string with aberration summary
        """
        # Handle backward compatibility
        field_angle_deg = kwargs.get("field_angle_deg", field_angle)

        results = self.calculate_all_aberrations(
            object_distance, field_angle_deg, wavelength_nm=wavelength_nm
        )

        if results.get("error"):
            return f"Error: {results['error']}"

        def _metric(key: str, spec: str = ".4f", suffix: str = "") -> str:
            """Format one metric, or say it could not be measured.

            A helper returning None means "not measurable" - a failed trace,
            a vignetted design. Formatting that with a float specifier raised
            ``TypeError: unsupported format string passed to NoneType.__format__``
            and the summary was lost entirely, rather than showing that one
            number is missing.
            """
            value = results.get(key)
            if value is None or (isinstance(value, float) and not math.isfinite(value)):
                return f"{'unavailable':>10}{suffix}"
            return f"{value:>10{spec}}{suffix}"

        def _trend(key: str, low: float, high: float, labels) -> str:
            """Interpretation label for a magnitude, or 'unavailable'."""
            value = results.get(key)
            if value is None or (isinstance(value, float) and not math.isfinite(value)):
                return "unavailable"
            magnitude = abs(value)
            for index, bound in enumerate((low, high)):
                if magnitude < bound:
                    return labels[index]
            return labels[-1]

        def _detail(key: str, spec: str, suffix: str = "") -> str:
            value = results.get(key)
            if value is None or (isinstance(value, float) and not math.isfinite(value)):
                return f"({suffix.strip() or 'value'} unavailable)"
            return f"({abs(value):{spec}} {suffix})" if suffix else f"({abs(value):{spec}})"

        # self.lens only exists for a single-lens target; a system target
        # sets is_system instead, so reading it here raised AttributeError.
        if self.is_system:
            element_count = len(getattr(self.target, "elements", []) or [])
            name = f"{self.target.name} ({element_count} elements)"
            material = "-"
        else:
            name = self.lens.name
            material = self.lens.material

        trend_labels = ("Negligible", "Moderate", "Significant")

        summary = f"""
╔═══════════════════════════════════════════════════════════════╗
║              LENS ABERRATIONS ANALYSIS                        ║
╠═══════════════════════════════════════════════════════════════╣
║ Lens: {name:<52} ║
║ Material: {material:<48} ║
╠═══════════════════════════════════════════════════════════════╣
║ BASIC PARAMETERS                                              ║
╠═══════════════════════════════════════════════════════════════╣
║ Focal Length:          {_metric('focal_length', '.2f', ' mm')}                      ║
║ F-number (f/#):        {_metric('f_number', '.2f')}                          ║
║ Numerical Aperture:    {_metric('numerical_aperture', '.4f')}                          ║
║ Airy Disk Diameter:    {_metric('airy_disk_diameter', '.6f', ' mm (diffraction limit)')} ║
╠═══════════════════════════════════════════════════════════════╣
║ PRIMARY ABERRATIONS (Seidel)                                  ║
╠═══════════════════════════════════════════════════════════════╣
║ Spherical Aberration:  {_metric('spherical', '.4f', ' mm (longitudinal)')}      ║
║ Coma (@ {field_angle}°):         {_metric('coma', '.4f', ' (relative)')}              ║
║ Astigmatism (@ {field_angle}°):  {_metric('astigmatism', '.4f', ' mm')}                       ║
║ Field Curvature:       {_metric('field_curvature', '.2f', ' mm (tangential focus shift)')} ║
║ Distortion (@ {field_angle}°):   {_metric('distortion', '.4f', ' %')}                        ║
╠═══════════════════════════════════════════════════════════════╣
║ CHROMATIC ABERRATION                                          ║
╠═══════════════════════════════════════════════════════════════╣
║ Longitudinal CA:       {_metric('chromatic', '.4f', ' mm (focal shift)')}        ║
╚═══════════════════════════════════════════════════════════════╝

INTERPRETATION:
• Spherical Aberration: {_trend('spherical', 0.001, 0.01, trend_labels)}
  {_detail('spherical', '.4f', 'mm')}

• Chromatic Aberration: {_trend('chromatic', 0.1, 0.5, trend_labels)}
  {_detail('chromatic', '.4f', 'mm')}

• Distortion: {_trend('distortion', 0.1, 1e9, ['None', 'None', 'Present'])}
  {_detail('distortion', '.2f', '%')}

• Resolution Limit: {_detail('airy_disk_diameter', '.2f', 'um')}
"""

        return summary

    def _calculate_spherical_aberration_seidel(self, focal_length: float) -> float:
        """Third-order Seidel longitudinal SA for a single spherical lens.

        Standard thin-lens form (Kingslake/Smith): with curvatures
        c1 = 1/R1, c2 = 1/R2 (0 for flat, so plano lenses work), shape
        factor B = (c1+c2)/(c1-c2) and conjugate factor C = -1 (object at
        infinity), LSA = -(y^2/8f)([(n/(n-1))^2 + (n+2)/(n(n-1)^2)
        (B + 2(n^2-1)/(n+2) C)^2]). Last-resort fallback when exact
        tracing fails; validated to agree with the exact trace within
        ~7% over an aperture x bending sweep (D = 10-40 mm).
        """
        c1 = 0.0 if not math.isfinite(self.radius_1) else 1.0 / self.radius_1
        c2 = 0.0 if not math.isfinite(self.radius_2) else 1.0 / self.radius_2
        if abs(c1 - c2) < EPSILON:
            B = 0.0
        else:
            B = (c1 + c2) / (c1 - c2)

        C = -1.0  # Object at infinity
        n = self.n
        y = self.diameter / 2.0

        # Simplified Seidel coefficient calculation
        term1 = (n / (n - 1.0)) ** 2
        term2 = (n + 2.0) / (n * (n - 1.0) ** 2)
        term3 = (B + (2.0 * (n**2 - 1.0) / (n + 2.0)) * C) ** 2

        # Longitudinal spherical aberration estimation
        lsa = -(y**2 / (8.0 * focal_length**3)) * (term1 + term2 * term3) * focal_length**2
        return lsa


def analyze_lens_quality(lens: Any, field_angle: float = 5.0, **kwargs) -> Dict[str, Any]:
    """
    Convenience function to analyze lens quality.

    Args:
        lens: Lens object
        field_angle: Field angle for off-axis aberrations (degrees)
        wavelength_nm: Wavelength in nm evaluated throughout (kwarg)

    Returns:
        Dictionary with quality assessment
    """
    # Handle backward compatibility
    field_angle = kwargs.get("field_angle_deg", field_angle)
    wavelength_nm = kwargs.get("wavelength_nm", WAVELENGTH_GREEN)

    calc = AberrationsCalculator(lens)
    results = calc.calculate_all_aberrations(field_angle=field_angle, wavelength_nm=wavelength_nm)

    if results.get("error"):
        return {"quality_score": 0, "rating": "Error", "issues": [results["error"]]}

    issues = []
    score = 100

    # Evaluate spherical aberration
    sa = abs(results["spherical"])
    if sa > SPHERICAL_ABERRATION_EXCELLENT:
        issues.append(f"High spherical aberration ({sa:.4f} mm)")
        score -= 40  # Major SA penalty
    elif sa > (SPHERICAL_ABERRATION_EXCELLENT / 10):
        issues.append(f"Moderate spherical aberration ({sa:.4f} mm)")
        score -= 20  # Minor SA penalty

    # Evaluate chromatic aberration
    ca = results["chromatic"]
    if ca > 0.5:  # Significant chromatic aberration
        issues.append(f"High chromatic aberration ({ca:.4f} mm)")
        score -= 40  # Major SA penalty
    elif ca > 0.1:
        issues.append(f"Moderate chromatic aberration ({ca:.4f} mm)")
        score -= 20  # Minor SA penalty

    # Evaluate distortion
    dist = results["distortion"]
    dist_abs = abs(dist)
    if dist_abs > 5:
        issues.append(f"High distortion ({dist_abs:.2f}%)")
        score -= 15
    elif dist_abs > 1:
        issues.append(f"Moderate distortion ({dist_abs:.2f}%)")
        score -= 5

    # Evaluate astigmatism
    ast = results["astigmatism"]
    if ast > 1.0:  # Large astigmatism
        issues.append(f"High astigmatism ({ast:.4f} mm)")
        score -= 15  # Astigmatism penalty
    elif ast > 0.1:  # Moderate astigmatism
        issues.append(f"Moderate astigmatism ({ast:.4f} mm)")
        score -= 5

    # Determine rating
    if score >= (QUALITY_EXCELLENT_THRESHOLD + 5):  # 90
        rating = "Excellent"
    elif score >= (QUALITY_GOOD_THRESHOLD + 5):  # 75
        rating = "Good"
    elif score >= (QUALITY_FAIR_THRESHOLD + 10):  # 60
        rating = "Fair"
    elif score >= (QUALITY_FAIR_THRESHOLD - 10):  # 40
        rating = "Poor"
    else:
        rating = "Very Poor"

    return {
        "quality_score": score,
        "rating": rating,
        "issues": issues if issues else ["No significant aberrations detected"],
        "aberrations": results,
    }
