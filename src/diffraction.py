"""
Diffraction Effects Module for OpenLens

Implements diffraction calculations including:
- Airy disk patterns
- Diffraction-limited resolution
- Point spread functions
- Numerical aperture effects

Requires:
- numpy
- scipy (for Bessel functions)
- matplotlib (for plotting)
"""

import numpy as np
from typing import Dict, Tuple, Optional

# Optional scipy import for Bessel functions
try:
    from scipy.special import j1  # Bessel function of first kind
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Warning: scipy not available. Diffraction calculations will use approximations.")
    
    # Fallback approximation for j1(x) Bessel function
    def j1(x):
        """Approximation of first-order Bessel function for small x"""
        if hasattr(x, '__iter__'):
            return np.array([j1(xi) for xi in x])
        # Taylor series approximation: J1(x) ≈ x/2 - x³/16 + x⁵/384
        x = float(x)
        if abs(x) < 0.1:
            return x/2.0 - x**3/16.0 + x**5/384.0
        # For larger x, use a simpler approximation
        return 0.5 * x * (1 - x**2/8.0)

# Optional matplotlib import
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("Warning: matplotlib not available. Plotting disabled for diffraction module.")


class DiffractionCalculator:
    """Calculate diffraction effects for optical systems"""
    
    def __init__(self, wavelength: float = 550e-9):
        """
        Initialize diffraction calculator
        
        Args:
            wavelength: Light wavelength in meters (default: 550nm green light)
        """
        self.wavelength = wavelength
    
    def airy_disk_radius(self, focal_length: float, aperture_diameter: float) -> float:
        """
        Calculate Airy disk radius (first zero of Airy pattern)
        
        Args:
            focal_length: Focal length in mm
            aperture_diameter: Aperture diameter in mm
        
        Returns:
            Airy disk radius in micrometers
        """
        # Convert to meters
        f = focal_length / 1000.0
        D = aperture_diameter / 1000.0
        
        # Airy disk radius: r = 1.22 * λ * f / D
        radius = 1.22 * self.wavelength * f / D
        
        # Convert to micrometers
        return radius * 1e6
    
    def rayleigh_criterion(self, aperture_diameter: float) -> float:
        """
        Calculate Rayleigh diffraction limit (angular resolution)
        
        Args:
            aperture_diameter: Aperture diameter in mm
        
        Returns:
            Angular resolution in arcseconds
        """
        # Convert to meters
        D = aperture_diameter / 1000.0
        
        # θ = 1.22 * λ / D (in radians)
        theta_rad = 1.22 * self.wavelength / D
        
        # Convert to arcseconds
        theta_arcsec = theta_rad * 206265
        
        return theta_arcsec
    
    def diffraction_limited_spot_size(self, f_number: float) -> float:
        """
        Calculate diffraction-limited spot size
        
        Args:
            f_number: F-number (f/D)
        
        Returns:
            Spot diameter in micrometers
        """
        # Spot diameter ≈ 2.44 * λ * f/#
        diameter = 2.44 * self.wavelength * f_number
        
        # Convert to micrometers
        return diameter * 1e6
    
    def numerical_aperture_resolution(self, numerical_aperture: float) -> float:
        """
        Calculate resolution limit based on numerical aperture
        
        Args:
            numerical_aperture: NA of the optical system
        
        Returns:
            Resolution limit in micrometers
        """
        # Resolution = 0.61 * λ / NA
        resolution = 0.61 * self.wavelength / numerical_aperture
        
        # Convert to micrometers
        return resolution * 1e6
    
    def airy_pattern(self, radius: float, focal_length: float, 
                     aperture_diameter: float, num_points: int = 1000) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate Airy diffraction pattern intensity
        
        Args:
            radius: Maximum radius to calculate (in micrometers)
            focal_length: Focal length in mm
            aperture_diameter: Aperture diameter in mm
            num_points: Number of points to calculate
        
        Returns:
            Tuple of (radii, intensities)
        """
        # Convert to meters
        f = focal_length / 1000.0
        D = aperture_diameter / 1000.0
        r_max = radius * 1e-6
        
        # Create radial coordinates
        r = np.linspace(0, r_max, num_points)
        
        # Calculate dimensionless parameter v = π * D * r / (λ * f)
        v = np.pi * D * r / (self.wavelength * f)
        
        # Avoid division by zero at center
        v[0] = 1e-10
        
        # Airy pattern: I(v) = I₀ * [2*J₁(v)/v]²
        intensity = (2 * j1(v) / v) ** 2
        
        # Normalize to peak intensity
        intensity = intensity / np.max(intensity)
        
        # Convert radius back to micrometers
        r_um = r * 1e6
        
        return r_um, intensity
    
    def point_spread_function_2d(self, size: float, focal_length: float,
                                  aperture_diameter: float, pixels: int = 256) -> np.ndarray:
        """
        Calculate 2D point spread function
        
        Args:
            size: Size of PSF region (in micrometers)
            focal_length: Focal length in mm
            aperture_diameter: Aperture diameter in mm
            pixels: Number of pixels per side
        
        Returns:
            2D array of PSF intensities
        """
        # Convert to meters
        f = focal_length / 1000.0
        D = aperture_diameter / 1000.0
        size_m = size * 1e-6
        
        # Create coordinate grid
        x = np.linspace(-size_m/2, size_m/2, pixels)
        y = np.linspace(-size_m/2, size_m/2, pixels)
        X, Y = np.meshgrid(x, y)
        
        # Calculate radial distance
        R = np.sqrt(X**2 + Y**2)
        
        # Calculate dimensionless parameter
        v = np.pi * D * R / (self.wavelength * f)
        
        # Avoid division by zero
        v[v == 0] = 1e-10
        
        # Calculate PSF
        psf = (2 * j1(v) / v) ** 2
        
        # Normalize
        psf = psf / np.max(psf)
        
        return psf
    
    def encircled_energy(self, focal_length: float, aperture_diameter: float,
                         max_radius: float = None, num_points: int = 100) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate encircled energy as function of radius
        
        Args:
            focal_length: Focal length in mm
            aperture_diameter: Aperture diameter in mm
            max_radius: Maximum radius in micrometers (default: 5x Airy disk)
            num_points: Number of points to calculate
        
        Returns:
            Tuple of (radii, encircled_energy_fraction)
        """
        if max_radius is None:
            airy_r = self.airy_disk_radius(focal_length, aperture_diameter)
            max_radius = 5 * airy_r
        
        # Get Airy pattern
        r, intensity = self.airy_pattern(max_radius, focal_length, aperture_diameter, num_points=1000)
        
        # Calculate encircled energy using cumulative integration
        # Energy at radius R = ∫∫ I(r) r dr dθ = 2π ∫ I(r) r dr
        dr = r[1] - r[0]
        energy_density = intensity * r * 2 * np.pi
        cumulative_energy = np.cumsum(energy_density) * dr
        
        # Normalize to total energy
        total_energy = cumulative_energy[-1]
        encircled = cumulative_energy / total_energy
        
        return r, encircled
    
    def calculate_metrics(self, focal_length: float, aperture_diameter: float) -> Dict:
        """
        Calculate comprehensive diffraction metrics
        
        Args:
            focal_length: Focal length in mm
            aperture_diameter: Aperture diameter in mm
        
        Returns:
            Dictionary of diffraction metrics
        """
        f_number = focal_length / aperture_diameter
        
        metrics = {
            'airy_disk_radius_um': self.airy_disk_radius(focal_length, aperture_diameter),
            'rayleigh_limit_arcsec': self.rayleigh_criterion(aperture_diameter),
            'diffraction_spot_um': self.diffraction_limited_spot_size(f_number),
            'f_number': f_number,
            'wavelength_nm': self.wavelength * 1e9
        }
        
        return metrics
    
    def plot_airy_disk(self, focal_length: float, aperture_diameter: float,
                       save_path: Optional[str] = None):
        """
        Plot Airy disk intensity pattern
        
        Args:
            focal_length: Focal length in mm
            aperture_diameter: Aperture diameter in mm
            save_path: Optional path to save the plot
        """
        airy_r = self.airy_disk_radius(focal_length, aperture_diameter)
        max_radius = 5 * airy_r
        
        r, intensity = self.airy_pattern(max_radius, focal_length, aperture_diameter)
        
        plt.figure(figsize=(10, 6))
        plt.plot(r, intensity, 'b-', linewidth=2)
        plt.axvline(x=airy_r, color='r', linestyle='--', 
                   label=f'Airy disk radius = {airy_r:.2f} μm')
        plt.axhline(y=0.5, color='g', linestyle=':', alpha=0.5)
        
        plt.xlabel('Radius (μm)')
        plt.ylabel('Normalized Intensity')
        plt.title(f'Airy Diffraction Pattern\n(f={focal_length}mm, D={aperture_diameter}mm, λ={self.wavelength*1e9:.0f}nm)')
        plt.grid(True, alpha=0.3)
        plt.legend()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
        
        plt.close()
    
    def plot_psf_2d(self, focal_length: float, aperture_diameter: float,
                    save_path: Optional[str] = None):
        """
        Plot 2D point spread function
        
        Args:
            focal_length: Focal length in mm
            aperture_diameter: Aperture diameter in mm
            save_path: Optional path to save the plot
        """
        airy_r = self.airy_disk_radius(focal_length, aperture_diameter)
        size = 10 * airy_r
        
        psf = self.point_spread_function_2d(size, focal_length, aperture_diameter)
        
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))
        
        # 2D PSF
        extent = [-size/2, size/2, -size/2, size/2]
        im = ax1.imshow(psf, extent=extent, cmap='hot', origin='lower')
        ax1.set_xlabel('X (μm)')
        ax1.set_ylabel('Y (μm)')
        ax1.set_title('2D Point Spread Function')
        plt.colorbar(im, ax=ax1, label='Normalized Intensity')
        
        # Cross-section
        center = psf.shape[0] // 2
        profile = psf[center, :]
        x_coords = np.linspace(-size/2, size/2, len(profile))
        ax2.plot(x_coords, profile, 'b-', linewidth=2)
        ax2.axvline(x=airy_r, color='r', linestyle='--', 
                   label=f'Airy disk radius = {airy_r:.2f} μm')
        ax2.axvline(x=-airy_r, color='r', linestyle='--')
        ax2.set_xlabel('Position (μm)')
        ax2.set_ylabel('Normalized Intensity')
        ax2.set_title('PSF Cross-Section')
        ax2.grid(True, alpha=0.3)
        ax2.legend()
        
        plt.suptitle(f'Point Spread Function Analysis\n(f={focal_length}mm, D={aperture_diameter}mm, λ={self.wavelength*1e9:.0f}nm)')
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
        
        plt.close()
    
    def plot_encircled_energy(self, focal_length: float, aperture_diameter: float,
                              save_path: Optional[str] = None):
        """
        Plot encircled energy curve
        
        Args:
            focal_length: Focal length in mm
            aperture_diameter: Aperture diameter in mm
            save_path: Optional path to save the plot
        """
        r, encircled = self.encircled_energy(focal_length, aperture_diameter)
        airy_r = self.airy_disk_radius(focal_length, aperture_diameter)
        
        plt.figure(figsize=(10, 6))
        plt.plot(r, encircled * 100, 'b-', linewidth=2)
        plt.axvline(x=airy_r, color='r', linestyle='--', 
                   label=f'Airy disk radius = {airy_r:.2f} μm')
        
        # Mark 50% and 80% energy
        idx_50 = np.argmin(np.abs(encircled - 0.5))
        idx_80 = np.argmin(np.abs(encircled - 0.8))
        plt.axhline(y=50, color='g', linestyle=':', alpha=0.5)
        plt.axhline(y=80, color='orange', linestyle=':', alpha=0.5)
        plt.plot(r[idx_50], 50, 'go', markersize=8, 
                label=f'50% @ {r[idx_50]:.2f} μm')
        plt.plot(r[idx_80], 80, 'o', color='orange', markersize=8,
                label=f'80% @ {r[idx_80]:.2f} μm')
        
        plt.xlabel('Radius (μm)')
        plt.ylabel('Encircled Energy (%)')
        plt.title(f'Encircled Energy Curve\n(f={focal_length}mm, D={aperture_diameter}mm, λ={self.wavelength*1e9:.0f}nm)')
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.ylim(0, 105)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
        
        plt.close()


if __name__ == "__main__":
    # Example usage
    print("=== Diffraction Calculator Demo ===\n")
    
    # Create calculator for green light
    calc = DiffractionCalculator(wavelength=550e-9)
    
    # Example lens parameters
    focal_length = 50.0  # mm
    aperture_diameter = 25.0  # mm
    
    # Calculate metrics
    metrics = calc.calculate_metrics(focal_length, aperture_diameter)
    
    print(f"Optical System: f={focal_length}mm, D={aperture_diameter}mm")
    print(f"Wavelength: {metrics['wavelength_nm']:.0f} nm")
    print(f"\nDiffraction Metrics:")
    print(f"  F-number: f/{metrics['f_number']:.1f}")
    print(f"  Airy disk radius: {metrics['airy_disk_radius_um']:.3f} μm")
    print(f"  Rayleigh limit: {metrics['rayleigh_limit_arcsec']:.3f} arcsec")
    print(f"  Diffraction spot: {metrics['diffraction_spot_um']:.3f} μm")
    
    # Generate plots
    print("\nGenerating plots...")
    calc.plot_airy_disk(focal_length, aperture_diameter)
    calc.plot_psf_2d(focal_length, aperture_diameter)
    calc.plot_encircled_energy(focal_length, aperture_diameter)
