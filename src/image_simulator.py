"""
Image Simulation Module
Simulates how test patterns and real images appear through the optical system.

Requires:
- numpy
- matplotlib
- PIL (Pillow)
- scipy (optional, for advanced image processing)
"""

import logging
import numpy as np
from typing import Tuple, Optional, Dict, Any

logger = logging.getLogger(__name__)

# Try importing PIL
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logger.warning("PIL/Pillow not available. Image loading disabled.")

# Try importing matplotlib
try:
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    logger.warning("matplotlib not available. Plotting disabled.")

# Try importing scipy (optional)
try:
    from scipy.ndimage import gaussian_filter, gaussian_filter1d, zoom, sobel
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    # Will use fallback implementations where needed


class ImageSimulator:
    """Simulates image formation through optical systems."""
    
    def __init__(self, optical_system):
        self.optical_system = optical_system
        self.test_patterns = {
            'grid': self._create_grid_pattern,
            'checkerboard': self._create_checkerboard_pattern,
            'star': self._create_star_pattern,
            'siemens_star': self._create_siemens_star,
            'text': self._create_text_pattern,
            'slant_edge': self._create_slant_edge
        }
        
    def simulate_image(self, input_image: np.ndarray,
                      object_distance: float,
                      image_distance: Optional[float] = None,
                      wavelength: float = 587.6) -> Dict[str, Any]:
        """
        Simulate image formation through the optical system.
        
        Args:
            input_image: Input image array (H, W, C) or (H, W)
            object_distance: Distance from lens to object
            image_distance: Distance from lens to image (None for auto)
            wavelength: Wavelength in nm
            
        Returns:
            Dictionary with simulated image and metrics
        """
        # Calculate image distance if not provided
        if image_distance is None:
            image_distance = self._calculate_image_distance(object_distance, wavelength)
        
        # Apply aberrations
        aberrated_image = self._apply_aberrations(
            input_image, object_distance, image_distance, wavelength
        )
        
        # Apply diffraction
        diffracted_image = self._apply_diffraction(
            aberrated_image, wavelength
        )
        
        # Apply chromatic aberration if color image
        if len(diffracted_image.shape) == 3:
            final_image = self._apply_chromatic_aberration(
                diffracted_image, object_distance, image_distance
            )
        else:
            final_image = diffracted_image
        
        # Apply vignetting
        final_image = self._apply_vignetting(final_image)
        
        # Calculate metrics
        metrics = self._calculate_image_metrics(input_image, final_image)
        
        return {
            'output_image': final_image,
            'magnification': -image_distance / object_distance,
            'image_distance': image_distance,
            'metrics': metrics
        }
    
    def simulate_test_pattern(self, pattern_name: str,
                             size: Tuple[int, int] = (512, 512),
                             **kwargs) -> Dict[str, Any]:
        """Simulate a test pattern through the system."""
        if pattern_name not in self.test_patterns:
            raise ValueError(f"Unknown pattern: {pattern_name}")
        
        # Extract object distance
        object_distance = kwargs.pop('object_distance', 100.0)
        
        # Generate test pattern
        pattern = self.test_patterns[pattern_name](size, **kwargs)
        
        # Simulate through system
        return self.simulate_image(pattern, object_distance)
    
    def _calculate_image_distance(self, object_distance: float, 
                                  wavelength: float) -> float:
        """Calculate image distance using lens equation."""
        if not hasattr(self.optical_system, 'effective_focal_length'):
            return object_distance  # Simple assumption
        
        f = self.optical_system.effective_focal_length(wavelength)
        
        if abs(object_distance - f) < 0.001:
            return float('inf')  # Object at focal point
        
        # 1/f = 1/s + 1/s'
        image_distance = 1.0 / (1.0 / f - 1.0 / object_distance)
        return abs(image_distance)
    
    def _apply_aberrations(self, image: np.ndarray,
                          object_distance: float,
                          image_distance: float,
                          wavelength: float) -> np.ndarray:
        """Apply optical aberrations to image."""
        if not SCIPY_AVAILABLE:
            # Fallback: return image without aberration simulation
            return image
        
        from scipy.ndimage import gaussian_filter, gaussian_filter1d
        
        # Get aberration coefficients
        if hasattr(self.optical_system, 'get_aberrations'):
            aberrations = self.optical_system.get_aberrations(wavelength)
        else:
            aberrations = {}
        
        result = image.copy()
        
        # Spherical aberration (blur increasing with radius)
        if 'spherical' in aberrations:
            coeff = abs(aberrations['spherical'])
            if coeff > 0:
                # Simple uniform blur (simplified)
                sigma = coeff * 2.0
                result = gaussian_filter(result, sigma=sigma)
        
        # Coma (asymmetric blur)
        if 'coma' in aberrations:
            coeff = abs(aberrations['coma'])
            if coeff > 0:
                result = gaussian_filter(result, sigma=coeff * 2)
        
        # Astigmatism
        if 'astigmatism' in aberrations:
            coeff = abs(aberrations['astigmatism'])
            if coeff > 0:
                # Blur more in one direction
                result = gaussian_filter1d(result, sigma=coeff * 2, axis=0)
        
        return result
    
    def _apply_diffraction(self, image: np.ndarray, wavelength: float) -> np.ndarray:
        """Apply diffraction-limited blur (PSF)."""
        if not SCIPY_AVAILABLE:
            # Fallback: return image without diffraction simulation
            return image
            
        from scipy.ndimage import gaussian_filter
        
        # Calculate diffraction-limited spot size
        if hasattr(self.optical_system, 'aperture_diameter'):
            diameter = self.optical_system.aperture_diameter
        else:
            diameter = 10.0  # Default 10mm
        
        # Airy disk radius
        if hasattr(self.optical_system, 'effective_focal_length'):
            f = self.optical_system.effective_focal_length(wavelength)
            airy_radius = 1.22 * wavelength * 1e-6 * f / diameter
        else:
            airy_radius = wavelength * 1e-6  # Simplified
        
        # Convert to pixels (assume 1 pixel = 1 micron)
        sigma_pixels = airy_radius * 1000 / 2.355  # FWHM to sigma
        
        return gaussian_filter(image, sigma=max(0.1, sigma_pixels))
    
    def _apply_chromatic_aberration(self, image: np.ndarray,
                                    object_distance: float,
                                    image_distance: float) -> np.ndarray:
        """Apply chromatic aberration (color fringing)."""
        if len(image.shape) != 3 or image.shape[2] < 3:
            return image
        
        if not SCIPY_AVAILABLE:
            # Fallback: return image without chromatic aberration simulation
            return image
        
        from scipy.ndimage import zoom
        
        result = image.copy()
        
        # Different wavelengths focus at different distances
        # Simulate by scaling each channel slightly differently
        wavelengths = [650, 550, 450]  # R, G, B
        base_wavelength = 550
        
        for i, wl in enumerate(wavelengths):
            if not hasattr(self.optical_system, 'effective_focal_length'):
                continue
            
            f_base = self.optical_system.effective_focal_length(base_wavelength)
            f_wl = self.optical_system.effective_focal_length(wl)
            
            # Calculate scale difference
            scale = f_wl / f_base
            
            if abs(scale - 1.0) > 0.0001:
                # Zoom channel
                h, w = result.shape[:2]
                zoomed = zoom(result[:, :, i], scale, order=1)
                
                # Crop/pad to original size
                zh, zw = zoomed.shape
                if zh > h:
                    start = (zh - h) // 2
                    zoomed = zoomed[start:start+h, :]
                elif zh < h:
                    pad = (h - zh) // 2
                    zoomed = np.pad(zoomed, ((pad, h-zh-pad), (0, 0)), mode='edge')
                
                if zw > w:
                    start = (zw - w) // 2
                    zoomed = zoomed[:, start:start+w]
                elif zw < w:
                    pad = (w - zw) // 2
                    zoomed = np.pad(zoomed, ((0, 0), (pad, w-zw-pad)), mode='edge')
                
                result[:, :, i] = zoomed[:h, :w]
        
        return result
    
    def _apply_vignetting(self, image: np.ndarray) -> np.ndarray:
        """Apply vignetting (brightness falloff at edges)."""
        h, w = image.shape[:2]
        y, x = np.ogrid[:h, :w]
        cy, cx = h / 2, w / 2
        
        # Radial distance from center
        r = np.sqrt((x - cx)**2 + (y - cy)**2)
        r_max = np.sqrt(cx**2 + cy**2)
        r_norm = r / r_max
        
        # Cos^4 falloff
        vignette = np.cos(r_norm * np.pi / 2) ** 4
        
        if len(image.shape) == 3:
            vignette = vignette[:, :, np.newaxis]
        
        return image * vignette
    
    def _calculate_image_metrics(self, original: np.ndarray, 
                                 simulated: np.ndarray) -> Dict[str, float]:
        """Calculate image quality metrics."""
        # Ensure same size
        if original.shape != simulated.shape:
            if SCIPY_AVAILABLE:
                from scipy.ndimage import zoom
                factors = np.array(simulated.shape[:2]) / np.array(original.shape[:2])
                original = zoom(original, factors, order=1)
            else:
                # Fallback: simple nearest neighbor resize using numpy
                h, w = simulated.shape[:2]
                original = np.array(Image.fromarray((original * 255).astype(np.uint8)).resize((w, h))) / 255.0 if PIL_AVAILABLE else original
        
        # PSNR
        mse = np.mean((original - simulated) ** 2)
        if mse > 0:
            psnr = 10 * np.log10(1.0 / mse)
        else:
            psnr = float('inf')
        
        # SSIM (simplified)
        ssim = self._calculate_ssim(original, simulated)
        
        # MTF at Nyquist
        mtf_nyquist = self._calculate_mtf_nyquist(simulated)
        
        return {
            'psnr': psnr,
            'ssim': ssim,
            'mtf_nyquist': mtf_nyquist,
            'sharpness': self._calculate_sharpness(simulated)
        }
    
    def _calculate_ssim(self, img1: np.ndarray, img2: np.ndarray) -> float:
        """Calculate structural similarity index (simplified)."""
        c1 = 0.01 ** 2
        c2 = 0.03 ** 2
        
        mu1 = img1.mean()
        mu2 = img2.mean()
        sigma1 = img1.std()
        sigma2 = img2.std()
        sigma12 = np.mean((img1 - mu1) * (img2 - mu2))
        
        ssim = ((2 * mu1 * mu2 + c1) * (2 * sigma12 + c2)) / \
               ((mu1**2 + mu2**2 + c1) * (sigma1**2 + sigma2**2 + c2))
        
        return float(ssim)
    
    def _calculate_mtf_nyquist(self, image: np.ndarray) -> float:
        """Calculate MTF at Nyquist frequency."""
        if len(image.shape) == 3:
            image = np.mean(image, axis=2)
        
        # FFT
        fft = np.fft.fft2(image)
        fft_shift = np.fft.fftshift(fft)
        magnitude = np.abs(fft_shift)
        
        # Nyquist frequency (half of sampling rate)
        h, w = magnitude.shape
        nyquist_idx = min(h, w) // 4
        
        # Average around Nyquist ring
        cy, cx = h // 2, w // 2
        y, x = np.ogrid[:h, :w]
        r = np.sqrt((x - cx)**2 + (y - cy)**2)
        
        mask = (r >= nyquist_idx - 2) & (r <= nyquist_idx + 2)
        mtf = magnitude[mask].mean() / magnitude[cy, cx]
        
        return float(mtf)
    
    def _calculate_sharpness(self, image: np.ndarray) -> float:
        """Calculate image sharpness using gradient magnitude."""
        if len(image.shape) == 3:
            image = np.mean(image, axis=2)
        
        if SCIPY_AVAILABLE:
            # Sobel gradients
            from scipy.ndimage import sobel
            dx = sobel(image, axis=1)
            dy = sobel(image, axis=0)
        else:
            # Fallback: simple gradient using numpy diff
            dx = np.diff(image, axis=1, prepend=0)
            dy = np.diff(image, axis=0, prepend=0)
        
        gradient_magnitude = np.sqrt(dx**2 + dy**2)
        return float(gradient_magnitude.mean())
    
    # Test pattern generators
    def _create_grid_pattern(self, size: Tuple[int, int], 
                            spacing: int = 50) -> np.ndarray:
        """Create grid test pattern."""
        h, w = size
        pattern = np.ones((h, w))
        pattern[::spacing, :] = 0
        pattern[:, ::spacing] = 0
        return pattern
    
    def _create_checkerboard_pattern(self, size: Tuple[int, int],
                                    square_size: int = 32) -> np.ndarray:
        """Create checkerboard pattern."""
        h, w = size
        pattern = np.zeros((h, w))
        
        for i in range(0, h, square_size):
            for j in range(0, w, square_size):
                if ((i // square_size) + (j // square_size)) % 2 == 0:
                    pattern[i:i+square_size, j:j+square_size] = 1
        
        return pattern
    
    def _create_star_pattern(self, size: Tuple[int, int],
                            num_rays: int = 8) -> np.ndarray:
        """Create star test pattern."""
        h, w = size
        y, x = np.ogrid[:h, :w]
        cy, cx = h // 2, w // 2
        
        angle = np.arctan2(y - cy, x - cx)
        pattern = np.cos(num_rays * angle) > 0
        
        return pattern.astype(float)
    
    def _create_siemens_star(self, size: Tuple[int, int],
                            num_spokes: int = 36) -> np.ndarray:
        """Create Siemens star resolution target."""
        h, w = size
        y, x = np.ogrid[:h, :w]
        cy, cx = h // 2, w // 2
        
        r = np.sqrt((x - cx)**2 + (y - cy)**2)
        angle = np.arctan2(y - cy, x - cx)
        
        pattern = np.sin(num_spokes * angle) > 0
        
        # Circular mask
        r_max = min(h, w) // 2
        pattern[r > r_max] = 0.5
        
        return pattern.astype(float)
    
    def _create_text_pattern(self, size: Tuple[int, int],
                            text: str = "TEST") -> np.ndarray:
        """Create text pattern."""
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('L', size, color=255)
        draw = ImageDraw.Draw(img)
        
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
        except (IOError, OSError) as e:
            logger.debug(f"Failed to load system font, using default: {e}")
            font = ImageFont.load_default()
        
        bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pos = ((size[1] - text_w) // 2, (size[0] - text_h) // 2)
        
        draw.text(pos, text, fill=0, font=font)
        
        return np.array(img) / 255.0
    
    def _create_slant_edge(self, size: Tuple[int, int],
                          angle: float = 5.0) -> np.ndarray:
        """Create slanted edge for MTF measurement."""
        h, w = size
        y, x = np.ogrid[:h, :w]
        
        angle_rad = np.radians(angle)
        edge = x * np.cos(angle_rad) + y * np.sin(angle_rad)
        edge = edge - edge[h//2, w//2]
        
        pattern = (edge > 0).astype(float)
        return pattern
