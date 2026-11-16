"""Zernike decomposition of the exit-pupil wavefront.

The wavefront sensor returns a sampled OPD map in waves. This module fits the
valid samples to the standard normalized Zernike basis, so coma, astigmatism,
trefoil, spherical and higher-order terms can be read in the units an
interferometer and a lens specification use.

The fit is a plain least-squares solve on the masked pupil, so vignetted or
obscured samples simply do not contribute. Coefficients are in waves.
"""

import math
from dataclasses import dataclass, field
from typing import List, Tuple

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on the environment
    np = None  # type: ignore[assignment]
    NUMPY_AVAILABLE = False

from ..constants import EPSILON

#: Default number of terms: the first 15 Noll terms, i.e. radial order 4.
DEFAULT_TERM_COUNT = 15

_TERM_NAMES = {
    (0, 0): "Piston",
    (1, 1): "Tilt X",
    (1, -1): "Tilt Y",
    (2, 0): "Defocus",
    (2, 2): "Astigmatism 0/90",
    (2, -2): "Astigmatism 45/135",
    (3, 1): "Coma X",
    (3, -1): "Coma Y",
    (3, 3): "Trefoil X",
    (3, -3): "Trefoil Y",
    (4, 0): "Primary spherical",
    (4, 2): "Secondary astigmatism 0/90",
    (4, -2): "Secondary astigmatism 45/135",
    (4, 4): "Quadrafoil X",
    (4, -4): "Quadrafoil Y",
    (5, 1): "Secondary coma X",
    (5, -1): "Secondary coma Y",
    (5, 3): "Secondary trefoil X",
    (5, -3): "Secondary trefoil Y",
    (5, 5): "Pentafoil X",
    (5, -5): "Pentafoil Y",
    (6, 0): "Secondary spherical",
}


@dataclass(frozen=True)
class ZernikeTerm:
    """One Zernike mode and its index in the requested convention.

    Attributes:
        index: Noll or OSA/ANSI index (1-based).
        n: Radial order.
        m: Azimuthal order; positive is cosine, negative is sine, zero is
            rotationally symmetric.
        name: Human-readable name, e.g. ``"Defocus"``.
    """

    index: int
    n: int
    m: int
    name: str


@dataclass
class ZernikeFit:
    """Result of fitting a sampled wavefront to a Zernike set.

    Attributes:
        indexing: ``"noll"`` or ``"osa"``.
        terms: The fitted modes, in ascending index order.
        coefficients: Coefficient per term, in waves.
        rms: RMS contribution per term over the fitted samples, in waves.
        residual_rms: RMS of the unmodelled remainder, in waves.
        fitted_fraction: Valid samples divided by the samples inside the
            nominal pupil, so obscured and vignetted pupils report how much of
            the aperture the fit saw.
        piston_tilt_removed: Whether a plane was subtracted before fitting.
        sample_count: Number of samples that entered the fit.
    """

    indexing: str
    terms: List[ZernikeTerm] = field(default_factory=list)
    coefficients: List[float] = field(default_factory=list)
    rms: List[float] = field(default_factory=list)
    residual_rms: float = 0.0
    fitted_fraction: float = 0.0
    piston_tilt_removed: bool = True
    sample_count: int = 0

    def rows(self) -> List[Tuple[int, str, float, float]]:
        """Return ``(index, name, coefficient, rms)`` rows for a table."""
        return [
            (term.index, term.name, coefficient, rms)
            for term, coefficient, rms in zip(self.terms, self.coefficients, self.rms)
        ]


def _radial(n: int, m: int, rho):
    """Radial Zernike polynomial R_n^|m| at *rho*."""
    m = abs(m)
    total = 0.0
    for s in range((n - m) // 2 + 1):
        coefficient = ((-1) ** s * math.factorial(n - s)) / (
            math.factorial(s) * math.factorial((n + m) // 2 - s) * math.factorial((n - m) // 2 - s)
        )
        total = total + coefficient * rho ** (n - 2 * s)
    return total


def zernike_value(term: ZernikeTerm, rho, theta):
    """Evaluate a normalized Zernike mode at polar pupil coordinates.

    Args:
        term: Mode to evaluate.
        rho: Normalized radial coordinate(s).
        theta: Azimuthal coordinate(s) in radians.

    Returns:
        The mode value, normalized so its mean square over the unit disc is 1.
    """
    radial = _radial(term.n, term.m, rho)
    if term.m == 0:
        return math.sqrt(term.n + 1) * radial
    scale = math.sqrt(2 * (term.n + 1))
    if term.m > 0:
        return scale * radial * np.cos(term.m * theta)
    return scale * radial * np.sin(-term.m * theta)


def _term_name(n: int, m: int) -> str:
    return _TERM_NAMES.get((n, m), f"Zernike (n={n}, m={m})")


def _normalize_indexing(indexing: str) -> str:
    """Return ``"noll"`` or ``"osa"``, rejecting unknown conventions."""
    key = indexing.strip().lower().replace("-", "/")
    if key == "noll":
        return "noll"
    if key in ("osa", "ansi", "osa/ansi"):
        return "osa"
    raise ValueError(f"unknown Zernike indexing {indexing!r}; use 'noll' or 'osa'")


def zernike_terms(count: int = DEFAULT_TERM_COUNT, indexing: str = "noll") -> List[ZernikeTerm]:
    """Return the first *count* Zernike terms in the requested ordering.

    Noll and OSA/ANSI use the same normalized polynomials; they differ only in
    the index and the order in which the signed azimuthal orders appear.

    Args:
        count: Number of terms, at least 1.
        indexing: ``"noll"`` (default) or ``"osa"`` / ``"ansi"`` /
            ``"osa/ansi"``.

    Returns:
        The terms in ascending index order.

    Raises:
        ValueError: If *count* is not positive or *indexing* is unknown.
    """
    if count < 1:
        raise ValueError("a Zernike set needs at least one term")
    convention = _normalize_indexing(indexing)

    terms: List[ZernikeTerm] = []
    if convention == "osa":
        index = 1
        n = 0
        while len(terms) < count:
            for m in range(-n, n + 1, 2):
                terms.append(ZernikeTerm(index, n, m, _term_name(n, m)))
                index += 1
                if len(terms) == count:
                    break
            n += 1
        return terms

    # Noll: pair each |m| group so the cosine term gets the even index and
    # the sine term the odd one, which reproduces the published table.
    index = 1
    n = 0
    while len(terms) < count:
        for magnitude in range(n % 2, n + 1, 2):
            if magnitude == 0:
                terms.append(ZernikeTerm(index, n, 0, _term_name(n, 0)))
                index += 1
            else:
                if index % 2 == 0:
                    signed = (magnitude, -magnitude)
                else:
                    signed = (-magnitude, magnitude)
                for m in signed:
                    terms.append(ZernikeTerm(index, n, m, _term_name(n, m)))
                    index += 1
            if len(terms) >= count:
                break
        n += 1
    return terms[:count]


def fit_zernike_wavefront(
    wavefront,
    terms: int = DEFAULT_TERM_COUNT,
    indexing: str = "noll",
    remove_piston_tilt: bool = True,
) -> ZernikeFit:
    """Fit a sampled pupil wavefront to the Zernike basis.

    Args:
        wavefront: A ``WavefrontError`` with ``Y``, ``Z`` (pupil coordinates)
            and ``W`` (wavefront error in waves). NaN samples are excluded.
        terms: Number of terms to fit, default 15 (radial order 4).
        indexing: ``"noll"`` (default) or ``"osa"``.
        remove_piston_tilt: Subtract a least-squares plane before fitting, so
            the reported aberrations are referenced to the chief ray. Set to
            False to include piston and tilt in the coefficients.

    Returns:
        The fitted terms, coefficients, per-term RMS, residual RMS and the
        fraction of the pupil that entered the fit.

    Raises:
        RuntimeError: If numpy is unavailable.
        ValueError: If the term count or indexing is invalid.
    """
    if not NUMPY_AVAILABLE:
        raise RuntimeError("Zernike fitting requires numpy")

    term_list = zernike_terms(terms, indexing)
    convention = _normalize_indexing(indexing)
    fit = ZernikeFit(
        indexing=convention,
        terms=term_list,
        coefficients=[0.0] * len(term_list),
        rms=[0.0] * len(term_list),
        piston_tilt_removed=remove_piston_tilt,
    )

    Y = np.asarray(wavefront.Y, dtype=float)
    Z = np.asarray(wavefront.Z, dtype=float)
    W = np.asarray(wavefront.W, dtype=float)
    if Y.size == 0 or Z.size == 0 or W.size == 0:
        return fit

    radius = max(float(np.max(np.abs(Y))), float(np.max(np.abs(Z))))
    if radius <= EPSILON:
        return fit

    rho = np.sqrt(Y**2 + Z**2) / radius
    theta = np.arctan2(Z, Y)
    inside = rho <= 1.0 + 1e-9
    valid = inside & np.isfinite(W)
    pupil_count = int(np.count_nonzero(inside))
    valid_count = int(np.count_nonzero(valid))
    fit.sample_count = valid_count
    fit.fitted_fraction = valid_count / pupil_count if pupil_count else 0.0
    if valid_count == 0:
        return fit

    w = W[valid]
    rho_valid = rho[valid]
    theta_valid = theta[valid]
    if remove_piston_tilt:
        plane = np.column_stack([np.ones_like(w), Y[valid] / radius, Z[valid] / radius])
        plane_coefficients, _, _, _ = np.linalg.lstsq(plane, w, rcond=None)
        w = w - plane @ plane_coefficients

    design = np.column_stack([zernike_value(term, rho_valid, theta_valid) for term in term_list])
    coefficients, _, _, _ = np.linalg.lstsq(design, w, rcond=None)
    fitted = design @ coefficients

    fit.coefficients = [float(value) for value in coefficients]
    fit.rms = [
        abs(float(value)) * math.sqrt(float(np.mean(column**2)))
        for value, column in zip(coefficients, design.T)
    ]
    fit.residual_rms = math.sqrt(float(np.mean((w - fitted) ** 2)))
    return fit
