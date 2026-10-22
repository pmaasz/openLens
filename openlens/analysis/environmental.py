import copy
import math
from typing import TYPE_CHECKING, Union

from ..air_index import REFERENCE_PRESSURE_ATM, calculate_air_index
from ..constants import ABSOLUTE_ZERO_C, EPSILON
from ..material_database import get_material_database
from ..optical_system import OpticalSystem
from ..validation import ValidationError

if TYPE_CHECKING:
    from ..lens import Lens


class EnvironmentalAnalyzer:
    """
    Analyzes optical system performance under environmental changes
    (Temperature and Pressure).
    """

    # Standard reference conditions
    REF_TEMP = 20.0  # °C
    REF_PRESSURE = REFERENCE_PRESSURE_ATM  # atm (101.325 kPa)
    DEFAULT_HOUSING_CTE = 23.6e-6  # 1/K, aluminium

    @staticmethod
    def calculate_air_index(
        wavelength_nm: float, temperature_c: float, pressure_atm: float
    ) -> float:
        """
        Calculate refractive index of air using the Edlen equation.

        Kept as an analyzer API for callers that already use it; the
        implementation lives in ``openlens.air_index`` so that ``Lens`` can
        apply the same correction without importing the analysis package.

        Args:
            wavelength_nm: Wavelength in nanometers
            temperature_c: Temperature in Celsius
            pressure_atm: Pressure in Atmospheres

        Returns:
            Absolute refractive index of air
        """
        return calculate_air_index(wavelength_nm, temperature_c, pressure_atm)

    @classmethod
    def apply_environment(
        cls,
        system: OpticalSystem,
        temperature_c: float,
        pressure_atm: float,
        housing_cte: float = 23.6e-6,
    ) -> OpticalSystem:
        """
        Create a new OpticalSystem with environmental effects applied.

        Args:
            system: The nominal optical system
            temperature_c: New temperature in °C
            pressure_atm: New pressure in atm
            housing_cte: Housing expansion coefficient in 1/K for air gaps
                (default aluminum 23.6e-6; steel ~12e-6, invar ~1e-6,
                plastics ~50-200e-6)

        Returns:
            A new OpticalSystem instance with perturbed parameters
        """
        # Deep copy the system
        new_system = copy.deepcopy(system)
        new_system.name = f"{system.name} (T={temperature_c}C, P={pressure_atm}atm)"

        db = get_material_database()

        delta_T_k = temperature_c - cls.REF_TEMP

        # 1. Update Elements (Glass)
        for element in new_system.elements:
            lens = element.lens

            # Get material properties
            mat = db.get_material(lens.material)

            # Get CTE (Coefficient of Thermal Expansion)
            # Default to BK7/standard glass if unknown (~7.1e-6)
            alpha_k = mat.thermal_expansion if mat else 7.1e-6

            # --- Apply Thermal Expansion to Geometry ---
            scaling_factor = 1.0 + alpha_k * delta_T_k

            # Radius
            lens.radius_of_curvature_1 *= scaling_factor
            lens.radius_of_curvature_2 *= scaling_factor

            # Thickness
            lens.thickness *= scaling_factor

            # Diameter (mechanical only, but good to update)
            lens.diameter *= scaling_factor

            # --- Apply Refractive Index Changes ---
            # Catalog glasses carry dn/dT data. A custom glass has no catalog
            # entry; asking the database anyway would silently replace its
            # index with the BK7 fallback. Model glass is analytic and has no
            # temperature coefficients either.
            # Record the ambient pressure on the lens itself: catalog indices
            # are relative to air at 1 atm, and every analysis refreshes the
            # index at its own wavelength. update_refractive_index() applies
            # the air correction from this value, so the conditioned index
            # survives that refresh instead of silently reverting.
            lens.pressure_atm = pressure_atm
            has_index_model = mat is not None or bool(getattr(lens, "model_glass_mode", False))
            if has_index_model:
                lens.update_refractive_index(temperature=temperature_c)

        # 2. Update Air Gaps (Housing Expansion)
        # Gaps scale with the housing CTE (parameter; defaults to aluminum).
        housing_alpha_k = housing_cte
        gap_scaling = 1.0 + housing_alpha_k * delta_T_k

        for gap in new_system.air_gaps:
            gap.thickness *= gap_scaling

        # 3. Update positions based on new thicknesses
        new_system._update_positions()

        return new_system

    @classmethod
    def condition_at_temperature(
        cls,
        target: Union["Lens", OpticalSystem],
        temperature_c: float,
        pressure_atm: float = REF_PRESSURE,
        housing_cte: float = DEFAULT_HOUSING_CTE,
    ) -> Union["Lens", OpticalSystem]:
        """Return a lens or system conditioned to *temperature_c*.

        The stored model is never mutated. A single lens is wrapped in a
        temporary system so it goes through the same thermal-expansion and
        dn/dT path as an assembly. At the reference conditions the original
        object is returned, which keeps existing simulations unchanged.

        Args:
            target: A single lens or an optical system.
            temperature_c: Operating temperature in Celsius.
            pressure_atm: Ambient pressure in atmospheres.
            housing_cte: Housing expansion coefficient for air gaps (1/K).

        Returns:
            The original target at reference conditions, otherwise a
            conditioned copy of the same kind.

        Raises:
            ValidationError: If the temperature is non-finite or below
                absolute zero.
        """
        if not math.isfinite(temperature_c):
            raise ValidationError("temperature must be a finite number")
        if temperature_c < ABSOLUTE_ZERO_C:
            raise ValidationError(
                f"temperature cannot be below absolute zero ({ABSOLUTE_ZERO_C:g}°C)"
            )

        at_reference_pressure = abs(pressure_atm - cls.REF_PRESSURE) < EPSILON

        if isinstance(target, OpticalSystem):
            if at_reference_pressure and all(
                abs(element.lens.temperature - temperature_c) < EPSILON
                for element in target.elements
            ):
                return target
            return cls.apply_environment(target, temperature_c, pressure_atm, housing_cte)

        lens = target
        if at_reference_pressure and abs(lens.temperature - temperature_c) < EPSILON:
            return lens

        wrapper = OpticalSystem(name=f"{lens.name} @ {temperature_c:g} °C")
        wrapper.add_lens(lens)
        conditioned = cls.apply_environment(wrapper, temperature_c, pressure_atm, housing_cte)
        return conditioned.elements[0].lens
