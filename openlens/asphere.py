"""Even-order polynomial asphere profiles.

A surface's sag is the base conic plus a sum of even-order terms::

    z(r) = conic_sag(r) + A4*r^4 + A6*r^6 + ... + A16*r^16

``coefficients`` is an ordered list starting at A4, matching the common
``EVENASPH`` convention and Zemax's ``PARM 2..8`` (``PARM 1`` is the unused
r^2 term).
"""

import math
from typing import Iterable, List, Sequence

from .constants import EPSILON

#: Radial orders represented by an ``asphere_coefficients_N`` list.
ASPHERE_ORDERS = (4, 6, 8, 10, 12, 14, 16)


def normalize_asphere_coefficients(
    coefficients: Iterable[float] | None,
    param_name: str = "asphere coefficients",
) -> List[float]:
    """Validate and normalize an even-asphere coefficient list.

    Args:
        coefficients: Ordered A4..A16 values, or None/empty for a surface
            with no polynomial terms.
        param_name: Parameter name for error messages.

    Returns:
        A plain list with trailing zero coefficients removed.

    Raises:
        ValueError: If the value is not a sequence of finite numbers or has
            more entries than ``ASPHERE_ORDERS``.
    """
    if coefficients is None:
        return []
    if isinstance(coefficients, (str, bytes)) or not isinstance(coefficients, Sequence):
        raise ValueError(f"{param_name} must be a list of numbers, got {coefficients!r}")
    if len(coefficients) > len(ASPHERE_ORDERS):
        raise ValueError(
            f"{param_name} supports at most {len(ASPHERE_ORDERS)} values "
            f"(A4..A16), got {len(coefficients)}"
        )

    values = []
    for index, value in enumerate(coefficients):
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"{param_name}[{index}] must be a number, got {value!r}") from None
        if not math.isfinite(number):
            raise ValueError(f"{param_name}[{index}] must be finite, got {number}")
        values.append(number)

    while values and values[-1] == 0.0:
        values.pop()
    return values


def is_asphere(coefficients: Sequence[float] | None) -> bool:
    """Whether a coefficient list describes a non-spherical polynomial."""
    if not coefficients:
        return False
    return any(abs(value) > EPSILON for value in coefficients)


def _domain_radius(radius: float, conic_constant: float) -> float:
    """Largest real radial height of the base conic (see lens._conic_sag)."""
    if abs(radius) > 1e10 or radius == 0:
        return float("inf")
    if conic_constant <= -1.0:
        return float("inf")
    return 1.0 / (abs(1.0 / radius) * math.sqrt(1.0 + conic_constant))


def asphere_sag(
    radius: float,
    conic_constant: float,
    coefficients: Sequence[float] | None,
    y: float,
) -> float:
    """Vertex-referenced sag of a conic base plus even polynomial terms.

    The base term matches ``Lens.get_sag_N`` for spherical and conic
    surfaces. The polynomial is evaluated at the signed height, so even
    orders keep the profile rotationally symmetric.
    """
    if abs(radius) > 1e10 or radius == 0:
        sag = 0.0
    else:
        y_abs = abs(y)
        domain = _domain_radius(radius, conic_constant)
        if math.isfinite(domain):
            y_abs = min(y_abs, domain)
        c = 1.0 / radius
        radicand = max(0.0, 1.0 - (1.0 + conic_constant) * (c * y_abs) ** 2)
        sag = c * y_abs * y_abs / (1.0 + math.sqrt(radicand))

    for order, coefficient in zip(ASPHERE_ORDERS, coefficients or ()):
        sag += coefficient * y**order
    return sag


def asphere_slope(
    radius: float,
    conic_constant: float,
    coefficients: Sequence[float] | None,
    y: float,
) -> float:
    """Meridional slope ``dz/dy`` of the asphere at height ``y``."""
    if abs(radius) > 1e10 or radius == 0:
        slope = 0.0
    else:
        c = 1.0 / radius
        radicand = max(1.0 - (1.0 + conic_constant) * (c * y) ** 2, EPSILON)
        slope = c * y / math.sqrt(radicand)

    for order, coefficient in zip(ASPHERE_ORDERS, coefficients or ()):
        slope += order * coefficient * y ** (order - 1)
    return slope
