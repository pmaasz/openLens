"""
Polarization Module for OpenLens

Implements polarization calculations including:
- Polarization states (linear, circular, elliptical)
- Jones matrices and vectors
- Brewster angle calculations
- Birefringent materials
- Fresnel equations with polarization
"""

import numpy as np
from typing import Tuple, Dict, Optional
import matplotlib.pyplot as plt
from dataclasses import dataclass


@dataclass
class PolarizationState:
    """Represents a polarization state using Jones vector"""
    jones_vector: np.ndarray  # Complex 2D vector
    
    @classmethod
    def linear_horizontal(cls):
        """Horizontally polarized light"""
        return cls(np.array([1.0 + 0j, 0.0 + 0j]))
    
    @classmethod
    def linear_vertical(cls):
        """Vertically polarized light"""
        return cls(np.array([0.0 + 0j, 1.0 + 0j]))
    
    @classmethod
    def linear_45(cls):
        """45° linear polarization"""
        return cls(np.array([1.0, 1.0]) / np.sqrt(2))
    
    @classmethod
    def linear_angle(cls, angle_deg: float):
        """Linear polarization at arbitrary angle"""
        angle_rad = np.radians(angle_deg)
        return cls(np.array([np.cos(angle_rad), np.sin(angle_rad)]))
    
    @classmethod
    def circular_right(cls):
        """Right circular polarization"""
        return cls(np.array([1.0, 1j]) / np.sqrt(2))
    
    @classmethod
    def circular_left(cls):
        """Left circular polarization"""
        return cls(np.array([1.0, -1j]) / np.sqrt(2))
    
    @classmethod
    def elliptical(cls, a: float, b: float, angle_deg: float = 0):
        """Elliptical polarization"""
        angle_rad = np.radians(angle_deg)
        cos_a = np.cos(angle_rad)
        sin_a = np.sin(angle_rad)
        
        # Rotation matrix
        jones = np.array([a * cos_a - 1j * b * sin_a,
                         a * sin_a + 1j * b * cos_a])
        norm = np.sqrt(np.abs(jones[0])**2 + np.abs(jones[1])**2)
        return cls(jones / norm)
    
    def intensity(self) -> float:
        """Calculate intensity (magnitude squared)"""
        return np.abs(self.jones_vector[0])**2 + np.abs(self.jones_vector[1])**2
    
    def apply_matrix(self, matrix: np.ndarray) -> 'PolarizationState':
        """Apply Jones matrix to transform polarization"""
        new_vector = matrix @ self.jones_vector
        return PolarizationState(new_vector)
    
    def degree_of_polarization(self) -> float:
        """Calculate degree of polarization (0-1)"""
        I_total = self.intensity()
        if I_total == 0:
            return 0.0
        return 1.0  # Pure state
    
    def stokes_parameters(self) -> np.ndarray:
        """Convert to Stokes parameters [S0, S1, S2, S3]"""
        Ex, Ey = self.jones_vector
        S0 = np.abs(Ex)**2 + np.abs(Ey)**2
        S1 = np.abs(Ex)**2 - np.abs(Ey)**2
        S2 = 2 * np.real(Ex * np.conj(Ey))
        S3 = 2 * np.imag(Ex * np.conj(Ey))
        return np.array([S0, S1, S2, S3])


class JonesMatrices:
    """Collection of common Jones matrices"""
    
    @staticmethod
    def linear_polarizer(angle_deg: float) -> np.ndarray:
        """Linear polarizer at angle"""
        theta = np.radians(angle_deg)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        return np.array([[cos_t**2, cos_t * sin_t],
                        [cos_t * sin_t, sin_t**2]])
    
    @staticmethod
    def quarter_wave_plate(fast_axis_angle_deg: float = 0) -> np.ndarray:
        """Quarter-wave plate (λ/4 retarder)"""
        theta = np.radians(fast_axis_angle_deg)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        
        # Rotation matrix
        R = np.array([[cos_t, sin_t],
                     [-sin_t, cos_t]])
        R_inv = R.T
        
        # QWP matrix in principal axes
        QWP = np.array([[1, 0],
                       [0, 1j]])
        
        return R_inv @ QWP @ R
    
    @staticmethod
    def half_wave_plate(fast_axis_angle_deg: float = 0) -> np.ndarray:
        """Half-wave plate (λ/2 retarder)"""
        theta = np.radians(fast_axis_angle_deg)
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        
        R = np.array([[cos_t, sin_t],
                     [-sin_t, cos_t]])
        R_inv = R.T
        
        # HWP matrix in principal axes
        HWP = np.array([[1, 0],
                       [0, -1]])
        
        return R_inv @ HWP @ R
    
    @staticmethod
    def rotator(angle_deg: float) -> np.ndarray:
        """Optical rotator (e.g., quartz)"""
        theta = np.radians(angle_deg)
        return np.array([[np.cos(theta), np.sin(theta)],
                        [-np.sin(theta), np.cos(theta)]])
    
    @staticmethod
    def retarder(phase_deg: float, fast_axis_angle_deg: float = 0) -> np.ndarray:
        """General retarder with arbitrary phase delay"""
        delta = np.radians(phase_deg)
        theta = np.radians(fast_axis_angle_deg)
        
        cos_t = np.cos(theta)
        sin_t = np.sin(theta)
        
        R = np.array([[cos_t, sin_t],
                     [-sin_t, cos_t]])
        R_inv = R.T
        
        # Retarder in principal axes
        retarder = np.array([[np.exp(-1j * delta/2), 0],
                            [0, np.exp(1j * delta/2)]])
        
        return R_inv @ retarder @ R


class PolarizationCalculator:
    """Calculate polarization effects in optical systems"""
    
    def __init__(self):
        self.matrices = JonesMatrices()
    
    def brewster_angle(self, n1: float, n2: float) -> float:
        """
        Calculate Brewster angle for interface
        
        Args:
            n1: Refractive index of first medium
            n2: Refractive index of second medium
        
        Returns:
            Brewster angle in degrees
        """
        theta_b = np.arctan(n2 / n1)
        return np.degrees(theta_b)
    
    def fresnel_coefficients(self, n1: float, n2: float, 
                            angle_deg: float) -> Dict[str, complex]:
        """
        Calculate Fresnel reflection and transmission coefficients
        
        Args:
            n1: Refractive index of incident medium
            n2: Refractive index of transmitted medium
            angle_deg: Incident angle in degrees
        
        Returns:
            Dictionary with r_s, r_p, t_s, t_p coefficients
        """
        theta1 = np.radians(angle_deg)
        
        # Snell's law for transmission angle
        sin_theta2 = (n1 / n2) * np.sin(theta1)
        
        # Check for total internal reflection
        if sin_theta2 > 1.0:
            # Total internal reflection
            return {
                'r_s': 1.0 + 0j,
                'r_p': 1.0 + 0j,
                't_s': 0.0 + 0j,
                't_p': 0.0 + 0j,
                'total_internal_reflection': True
            }
        
        theta2 = np.arcsin(sin_theta2)
        
        cos_theta1 = np.cos(theta1)
        cos_theta2 = np.cos(theta2)
        
        # Fresnel coefficients for s-polarization (TE)
        r_s = (n1 * cos_theta1 - n2 * cos_theta2) / (n1 * cos_theta1 + n2 * cos_theta2)
        t_s = (2 * n1 * cos_theta1) / (n1 * cos_theta1 + n2 * cos_theta2)
        
        # Fresnel coefficients for p-polarization (TM)
        r_p = (n2 * cos_theta1 - n1 * cos_theta2) / (n2 * cos_theta1 + n1 * cos_theta2)
        t_p = (2 * n1 * cos_theta1) / (n2 * cos_theta1 + n1 * cos_theta2)
        
        return {
            'r_s': r_s,
            'r_p': r_p,
            't_s': t_s,
            't_p': t_p,
            'theta_transmitted_deg': np.degrees(theta2),
            'total_internal_reflection': False
        }
    
    def reflectance_transmittance(self, n1: float, n2: float, 
                                   angle_deg: float) -> Dict[str, float]:
        """
        Calculate reflectance and transmittance (power)
        
        Args:
            n1: Refractive index of incident medium
            n2: Refractive index of transmitted medium
            angle_deg: Incident angle in degrees
        
        Returns:
            Dictionary with R_s, R_p, T_s, T_p values
        """
        coeffs = self.fresnel_coefficients(n1, n2, angle_deg)
        
        if coeffs['total_internal_reflection']:
            return {
                'R_s': 1.0,
                'R_p': 1.0,
                'T_s': 0.0,
                'T_p': 0.0
            }
        
        theta1 = np.radians(angle_deg)
        theta2 = np.radians(coeffs['theta_transmitted_deg'])
        
        # Reflectance (power)
        R_s = np.abs(coeffs['r_s'])**2
        R_p = np.abs(coeffs['r_p'])**2
        
        # Transmittance (power with angle correction)
        T_s = (n2 * np.cos(theta2)) / (n1 * np.cos(theta1)) * np.abs(coeffs['t_s'])**2
        T_p = (n2 * np.cos(theta2)) / (n1 * np.cos(theta1)) * np.abs(coeffs['t_p'])**2
        
        return {
            'R_s': R_s,
            'R_p': R_p,
            'T_s': T_s,
            'T_p': T_p
        }
    
    def birefringence_retardance(self, delta_n: float, thickness_mm: float, 
                                 wavelength_nm: float) -> float:
        """
        Calculate phase retardance for birefringent material
        
        Args:
            delta_n: Birefringence (n_e - n_o)
            thickness_mm: Material thickness in mm
            wavelength_nm: Wavelength in nm
        
        Returns:
            Phase retardance in degrees
        """
        thickness_m = thickness_mm / 1000.0
        wavelength_m = wavelength_nm * 1e-9
        
        # Phase difference in radians
        delta_rad = 2 * np.pi * delta_n * thickness_m / wavelength_m
        
        return np.degrees(delta_rad) % 360
    
    def malus_law(self, incident_intensity: float, angle_deg: float) -> float:
        """
        Calculate transmitted intensity through polarizer (Malus' law)
        
        Args:
            incident_intensity: Incident light intensity
            angle_deg: Angle between polarizer and polarization
        
        Returns:
            Transmitted intensity
        """
        theta = np.radians(angle_deg)
        return incident_intensity * np.cos(theta)**2
    
    def plot_fresnel_curves(self, n1: float, n2: float, 
                           save_path: Optional[str] = None):
        """
        Plot Fresnel reflectance vs angle
        
        Args:
            n1: Refractive index of incident medium
            n2: Refractive index of transmitted medium
            save_path: Optional path to save plot
        """
        angles = np.linspace(0, 90, 500)
        R_s = []
        R_p = []
        
        for angle in angles:
            rt = self.reflectance_transmittance(n1, n2, angle)
            R_s.append(rt['R_s'])
            R_p.append(rt['R_p'])
        
        brewster = self.brewster_angle(n1, n2)
        critical_angle = None
        if n1 > n2:
            critical_angle = np.degrees(np.arcsin(n2 / n1))
        
        plt.figure(figsize=(10, 6))
        plt.plot(angles, R_s, 'b-', linewidth=2, label='s-polarization (TE)')
        plt.plot(angles, R_p, 'r-', linewidth=2, label='p-polarization (TM)')
        
        plt.axvline(x=brewster, color='g', linestyle='--', 
                   label=f'Brewster angle = {brewster:.2f}°')
        
        if critical_angle:
            plt.axvline(x=critical_angle, color='orange', linestyle='--',
                       label=f'Critical angle = {critical_angle:.2f}°')
        
        plt.xlabel('Incident Angle (degrees)')
        plt.ylabel('Reflectance')
        plt.title(f'Fresnel Reflectance Curves\n(n₁={n1:.3f}, n₂={n2:.3f})')
        plt.grid(True, alpha=0.3)
        plt.legend()
        plt.xlim(0, 90)
        plt.ylim(0, 1.05)
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
        
        plt.close()
    
    def plot_polarization_ellipse(self, state: PolarizationState,
                                   save_path: Optional[str] = None):
        """
        Plot polarization ellipse
        
        Args:
            state: Polarization state to plot
            save_path: Optional path to save plot
        """
        # Generate ellipse
        t = np.linspace(0, 2*np.pi, 1000)
        Ex, Ey = state.jones_vector
        
        x = np.real(Ex * np.exp(1j * t))
        y = np.real(Ey * np.exp(1j * t))
        
        plt.figure(figsize=(8, 8))
        plt.plot(x, y, 'b-', linewidth=2)
        plt.arrow(0, 0, x[0], y[0], head_width=0.05, head_length=0.05, 
                 fc='r', ec='r', linewidth=2)
        
        plt.axhline(y=0, color='k', linestyle='-', alpha=0.3)
        plt.axvline(x=0, color='k', linestyle='-', alpha=0.3)
        
        plt.xlabel('Ex')
        plt.ylabel('Ey')
        plt.title('Polarization Ellipse')
        plt.grid(True, alpha=0.3)
        plt.axis('equal')
        
        # Add Stokes parameters
        stokes = state.stokes_parameters()
        textstr = f'Stokes: [{stokes[0]:.2f}, {stokes[1]:.2f}, {stokes[2]:.2f}, {stokes[3]:.2f}]'
        plt.text(0.02, 0.98, textstr, transform=plt.gca().transAxes,
                verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
        else:
            plt.show()
        
        plt.close()


if __name__ == "__main__":
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
    print(f"  R_s = {rt['R_s']:.4f} ({rt['R_s']*100:.2f}%)")
    print(f"  R_p = {rt['R_p']:.4f} ({rt['R_p']*100:.2f}%)")
    print(f"  T_s = {rt['T_s']:.4f} ({rt['T_s']*100:.2f}%)")
    print(f"  T_p = {rt['T_p']:.4f} ({rt['T_p']*100:.2f}%)")
    
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
