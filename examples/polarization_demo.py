"""Polarization calculator demo.

Run with ``python3 examples/polarization_demo.py``. Moved out of
``openlens/polarization.py`` so the library module does not print (#478).
"""

from openlens.polarization import JonesMatrices, PolarizationCalculator, PolarizationState


def main() -> None:
    print("=== Polarization Calculator Demo ===\n")

    calc = PolarizationCalculator()

    # Example 1: Brewster angle
    n_air = 1.0
    n_glass = 1.5
    brewster = calc.brewster_angle(n_air, n_glass)
    print(f"Brewster angle (air→glass): {brewster:.2f}°")

    # Example 2: Fresnel coefficients
    angle = 45.0
    coeffs = calc.fresnel_coefficients(n_air, n_glass, angle)
    print(f"\nFresnel coefficients at {angle}°:")
    print(f"  r_s = {coeffs['r_s']:.4f}")
    print(f"  r_p = {coeffs['r_p']:.4f}")

    # Example 3: Reflectance/Transmittance
    rt = calc.reflectance_transmittance(n_air, n_glass, angle)
    print(f"\nReflectance/Transmittance at {angle}°:")
    print(f"  R_s = {rt['R_s']:.4f} ({rt['R_s'] * 100:.2f}%)")
    print(f"  R_p = {rt['R_p']:.4f} ({rt['R_p'] * 100:.2f}%)")
    print(f"  T_s = {rt['T_s']:.4f} ({rt['T_s'] * 100:.2f}%)")
    print(f"  T_p = {rt['T_p']:.4f} ({rt['T_p'] * 100:.2f}%)")

    # Example 4: Polarization states
    print("\n=== Polarization States ===")

    # Linear horizontal through QWP to get circular
    h_pol = PolarizationState.linear_horizontal()
    qwp = JonesMatrices.quarter_wave_plate(0)
    circular = h_pol.apply_matrix(qwp)

    print("\nHorizontal → QWP → Circular:")
    print(f"  Input Stokes: {h_pol.stokes_parameters()}")
    print(f"  Output Stokes: {circular.stokes_parameters()}")

    # Plot Fresnel curves
    print("\nGenerating Fresnel curves plot...")
    calc.plot_fresnel_curves(n_air, n_glass)

    # Plot polarization ellipse
    print("Generating polarization ellipse plot...")
    calc.plot_polarization_ellipse(circular)


if __name__ == "__main__":
    main()
