"""Refractive index of air.

The Edlen dispersion formula and its ideal-gas temperature/pressure scaling.
It lives in a module of its own because two layers need it: the environmental
analyzer conditions a system to an ambient pressure, and ``Lens`` re-applies
that same correction every time it resolves a catalog index (the analyses
refresh the index at their own wavelength). Importing the analysis package
from the model would be a cycle.

The reference conditions match the glass catalogs: 20 degrees Celsius and
1 atm.
"""

from .constants import ABSOLUTE_ZERO_C

REFERENCE_PRESSURE_ATM = 1.0
# The dispersion formula is defined for standard air at 15 degrees Celsius;
# 288.15 K is the reference temperature in the ideal-gas scaling below.
STANDARD_AIR_TEMPERATURE_K = 288.15


def calculate_air_index(wavelength_nm: float, temperature_c: float, pressure_atm: float) -> float:
    """Calculate the refractive index of air using the Edlen equation.

    Args:
        wavelength_nm: Wavelength in nanometers.
        temperature_c: Temperature in Celsius.
        pressure_atm: Pressure in atmospheres.

    Returns:
        Absolute refractive index of air.
    """
    # Convert wavelength to microns.
    wl_um = wavelength_nm / 1000.0
    if wl_um <= 0:
        return 1.0

    # Dispersion formula for standard air (15 degrees C, 1013.25 mbar, dry).
    # (n-1) * 10^8; formula from NIST / Ciddor (simplified Edlen).
    s2 = 1.0 / (wl_um * wl_um)
    n_s_minus_1_e8 = 8342.54 + 2406147.0 / (130.0 - s2) + 15998.0 / (38.9 - s2)
    n_s_minus_1 = n_s_minus_1_e8 * 1e-8

    # Temperature and pressure correction: P in Pa, T in K.
    p_pa = pressure_atm * 101325.0
    t_k = temperature_c - ABSOLUTE_ZERO_C

    # At absolute zero the ideal-gas model is singular. The simulator still
    # allows 0 K as the lower bound, so treat the remaining medium as vacuum
    # rather than dividing by zero.
    if t_k <= 0:
        return 1.0

    # Ideal-gas approximation:
    # n_tp - 1 = (n_s - 1) * (P / 101325) * (288.15 / T)
    return 1.0 + n_s_minus_1 * (p_pa / 101325.0) * (STANDARD_AIR_TEMPERATURE_K / t_k)
