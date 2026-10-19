"""Diffraction calculator demo.

Run with ``python3 examples/diffraction_demo.py``. Moved out of
``openlens/diffraction.py`` so the library module does not print (#478).
"""

from openlens.diffraction import DiffractionCalculator


def main() -> None:
    print("=== Diffraction Calculator Demo ===\n")

    # Create calculator for green light
    calc = DiffractionCalculator(wavelength_m=550e-9)

    # Example lens parameters
    focal_length = 50.0  # mm
    aperture_diameter = 25.0  # mm

    # Calculate metrics
    metrics = calc.calculate_metrics(focal_length, aperture_diameter)

    print(f"Optical System: f={focal_length}mm, D={aperture_diameter}mm")
    print(f"Wavelength: {metrics['wavelength_nm']:.0f} nm")
    print("\nDiffraction Metrics:")
    print(f"  F-number: f/{metrics['f_number']:.1f}")
    print(f"  Airy disk radius: {metrics['airy_disk_radius_um']:.3f} μm")
    print(f"  Rayleigh limit: {metrics['rayleigh_limit_arcsec']:.3f} arcsec")
    print(f"  Diffraction spot: {metrics['diffraction_spot_um']:.3f} μm")

    # Generate plots
    print("\nGenerating plots...")
    calc.plot_airy_disk(focal_length, aperture_diameter)
    calc.plot_psf_2d(focal_length, aperture_diameter)
    calc.plot_encircled_energy(focal_length, aperture_diameter)


if __name__ == "__main__":
    main()
