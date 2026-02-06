"""
Service Layer for openlens

Provides business logic services that decouple data access from
presentation and handle complex operations with proper error handling.
"""

from typing import Optional, Dict, List, Tuple, Any
from datetime import datetime


class LensService:
    """
    Service for lens-related business logic.
    
    Decouples lens operations from GUI and handles material
    database integration transparently.
    """
    
    def __init__(self, lens_manager, material_db=None):
        """
        Initialize lens service.
        
        Args:
            lens_manager: LensManager instance for persistence
            material_db: Optional MaterialDatabase instance
        """
        self.lens_manager = lens_manager
        self.material_db = material_db
    
    def _get_default_index(self, material: str) -> float:
        """Get default refractive index for common materials"""
        default_indices = {
            "BK7": 1.5168,
            "Fused Silica": 1.4585,
            "SF11": 1.78,
            "Crown Glass": 1.52,
            "Flint Glass": 1.65,
            "Sapphire": 1.77
        }
        return default_indices.get(material, 1.5168)
    
    def create_lens(self, name: str, radius1: float, radius2: float,
                   thickness: float, diameter: float, 
                   material: str = "BK7", 
                   wavelength: float = 587.6,
                   temperature: float = 20.0) -> 'Lens':
        """
        Create a new lens with proper material database integration.
        
        Args:
            name: Lens name
            radius1: Front surface radius (mm)
            radius2: Back surface radius (mm)
            thickness: Center thickness (mm)
            diameter: Lens diameter (mm)
            material: Material name
            wavelength: Design wavelength (nm)
            temperature: Operating temperature (°C)
        
        Returns:
            Lens: Created lens instance
        """
        from lens_editor import Lens
        
        # Get refractive index from material database if available
        if self.material_db and hasattr(self.material_db, 'get_material'):
            mat = self.material_db.get_material(material)
            if mat:
                refractive_index = self.material_db.get_refractive_index(
                    material, wavelength, temperature
                )
            else:
                # Fallback to default values
                refractive_index = self._get_default_index(material)
        else:
            refractive_index = self._get_default_index(material)
        
        lens = Lens(
            name=name,
            radius_of_curvature_1=radius1,
            radius_of_curvature_2=radius2,
            thickness=thickness,
            diameter=diameter,
            refractive_index=refractive_index,
            material=material,
            wavelength=wavelength,
            temperature=temperature
        )
        
        self.lens_manager.lenses.append(lens)
        self.lens_manager.save_lenses()
        return lens
    
    def update_lens(self, lens: 'Lens', **kwargs) -> bool:
        """
        Update lens properties with validation.
        
        Args:
            lens: Lens to update
            **kwargs: Properties to update
        
        Returns:
            bool: Success status
        """
        from validation import (
            validate_radius, validate_thickness, 
            validate_diameter, validate_refractive_index,
            ValidationError
        )
        
        try:
            # Validate before updating
            if 'radius_of_curvature_1' in kwargs:
                kwargs['radius_of_curvature_1'] = validate_radius(
                    kwargs['radius_of_curvature_1'], 
                    param_name="Radius 1"
                )
            
            if 'radius_of_curvature_2' in kwargs:
                kwargs['radius_of_curvature_2'] = validate_radius(
                    kwargs['radius_of_curvature_2'],
                    param_name="Radius 2"
                )
            
            if 'thickness' in kwargs:
                kwargs['thickness'] = validate_thickness(kwargs['thickness'])
            
            if 'diameter' in kwargs:
                kwargs['diameter'] = validate_diameter(kwargs['diameter'])
            
            if 'refractive_index' in kwargs:
                kwargs['refractive_index'] = validate_refractive_index(
                    kwargs['refractive_index']
                )
            
            # Update lens properties
            for key, value in kwargs.items():
                if hasattr(lens, key):
                    setattr(lens, key, value)
            
            # Update modified timestamp
            lens.modified_at = datetime.now().isoformat()
            
            # If material changed, update refractive index
            if 'material' in kwargs and self.material_db:
                if self.material_db.has_material(kwargs['material']):
                    lens.refractive_index = self.material_db.get_refractive_index(
                        kwargs['material'],
                        lens.wavelength,
                        lens.temperature
                    )
            
            # Save changes
            self.lens_manager.save_lenses()
            return True
            
        except ValidationError as e:
            print(f"Validation error: {e}")
            return False
        except Exception as e:
            print(f"Error updating lens: {e}")
            return False
    
    def calculate_optical_properties(self, lens: 'Lens') -> Dict[str, float]:
        """
        Calculate all optical properties for a lens.
        
        Args:
            lens: Lens to calculate properties for
        
        Returns:
            Dict with calculated properties
        """
        try:
            focal_length = lens.calculate_focal_length()
            optical_power = lens.calculate_optical_power()
            
            return {
                'focal_length': focal_length,
                'optical_power': optical_power,
                'f_number': focal_length / lens.diameter if lens.diameter > 0 else float('inf'),
                'numerical_aperture': lens.diameter / (2 * abs(focal_length)) if focal_length != 0 else 0
            }
        except Exception as e:
            print(f"Error calculating properties: {e}")
            return {
                'focal_length': float('inf'),
                'optical_power': 0.0,
                'f_number': float('inf'),
                'numerical_aperture': 0.0
            }
    
    def get_available_materials(self) -> List[str]:
        """
        Get list of available materials.
        
        Returns:
            List of material names
        """
        if self.material_db:
            return self.material_db.list_materials()
        else:
            # Fallback to common materials
            return ["BK7", "Fused Silica", "Crown Glass", "SF11", "Sapphire"]
    
    def duplicate_lens(self, lens: 'Lens', new_name: Optional[str] = None) -> 'Lens':
        """
        Create a duplicate of a lens.
        
        Args:
            lens: Lens to duplicate
            new_name: Optional new name for the duplicate
        
        Returns:
            Duplicated lens instance
        """
        from lens_editor import Lens
        
        data = lens.to_dict()
        data.pop('id')
        data.pop('created_at')
        
        if new_name:
            data['name'] = new_name
        else:
            data['name'] = f"{data['name']} (Copy)"
        
        new_lens = Lens.from_dict(data)
        self.lens_manager.lenses.append(new_lens)
        self.lens_manager.save_lenses()
        
        return new_lens


class CalculationService:
    """
    Service for optical calculations and analysis.
    
    Provides a clean interface for complex calculations without
    tight coupling to specific calculation modules.
    """
    
    def __init__(self):
        """Initialize calculation service"""
        self._aberrations_available = False
        self._ray_tracer_available = False
        
        # Try to import optional calculation modules
        try:
            from aberrations import AberrationsCalculator
            self._aberrations_available = True
        except ImportError:
            pass
        
        try:
            from ray_tracer import LensRayTracer
            self._ray_tracer_available = True
        except ImportError:
            pass
    
    def calculate_aberrations(self, lens: 'Lens', 
                            aperture: Optional[float] = None,
                            field_angle: float = 0.0) -> Optional[Dict[str, float]]:
        """
        Calculate aberrations for a lens.
        
        Args:
            lens: Lens to analyze
            aperture: Optional semi-aperture (default: diameter/2)
            field_angle: Field angle in degrees
        
        Returns:
            Dict with aberration values or None if not available
        """
        if not self._aberrations_available:
            return None
        
        try:
            from aberrations import AberrationsCalculator
            
            if aperture is None:
                aperture = lens.diameter / 2.0
            
            calc = AberrationsCalculator(lens, aperture=aperture, 
                                        field_angle=field_angle)
            return calc.calculate_all_aberrations()
        except Exception as e:
            print(f"Error calculating aberrations: {e}")
            return None
    
    def trace_rays(self, lens: 'Lens', 
                  num_rays: int = 11,
                  ray_type: str = 'parallel') -> Optional[List]:
        """
        Trace rays through a lens.
        
        Args:
            lens: Lens to trace through
            num_rays: Number of rays to trace
            ray_type: 'parallel' or 'point_source'
        
        Returns:
            List of traced rays or None if not available
        """
        if not self._ray_tracer_available:
            return None
        
        try:
            from ray_tracer import LensRayTracer
            
            tracer = LensRayTracer(lens)
            
            if ray_type == 'parallel':
                return tracer.trace_parallel_rays(num_rays=num_rays)
            elif ray_type == 'point_source':
                return tracer.trace_point_source(
                    source_position=[-100, 0, 0],
                    num_rays=num_rays
                )
            else:
                raise ValueError(f"Unknown ray type: {ray_type}")
        except Exception as e:
            print(f"Error tracing rays: {e}")
            return None
    
    def assess_lens_quality(self, lens: 'Lens') -> Optional[Dict[str, Any]]:
        """
        Assess overall lens quality.
        
        Args:
            lens: Lens to assess
        
        Returns:
            Dict with quality metrics or None if not available
        """
        if not self._aberrations_available:
            return None
        
        try:
            from aberrations import analyze_lens_quality
            return analyze_lens_quality(lens)
        except Exception as e:
            print(f"Error assessing quality: {e}")
            return None
    
    def is_aberrations_available(self) -> bool:
        """Check if aberrations calculations are available"""
        return self._aberrations_available
    
    def is_ray_tracing_available(self) -> bool:
        """Check if ray tracing is available"""
        return self._ray_tracer_available


class MaterialDatabaseService:
    """
    Service for material database operations.
    
    Provides consistent interface regardless of whether material
    database is available, with intelligent fallbacks.
    """
    
    def __init__(self):
        """Initialize material database service"""
        self.db = None
        self._available = False
        
        try:
            from material_database import get_material_database
            self.db = get_material_database()
            self._available = True
        except ImportError:
            pass
    
    def is_available(self) -> bool:
        """Check if material database is available"""
        return self._available
    
    def get_materials(self) -> List[str]:
        """
        Get list of available materials.
        
        Returns:
            List of material names
        """
        if self._available and self.db:
            return self.db.list_materials()
        else:
            # Fallback to basic materials
            return [
                "BK7",
                "Fused Silica", 
                "Crown Glass",
                "Flint Glass",
                "SF11",
                "Sapphire"
            ]
    
    def get_refractive_index(self, material: str, 
                           wavelength: float = 587.6,
                           temperature: float = 20.0) -> float:
        """
        Get refractive index for a material.
        
        Args:
            material: Material name
            wavelength: Wavelength in nm
            temperature: Temperature in °C
        
        Returns:
            Refractive index
        """
        if self._available and self.db:
            try:
                return self.db.get_refractive_index(material, wavelength, temperature)
            except:
                pass
        
        # Fallback to defaults
        defaults = {
            "BK7": 1.5168,
            "Fused Silica": 1.4585,
            "Crown Glass": 1.52,
            "Flint Glass": 1.65,
            "SF11": 1.78,
            "Sapphire": 1.77
        }
        return defaults.get(material, 1.5168)
    
    def get_material_info(self, material: str) -> Dict[str, Any]:
        """
        Get detailed information about a material.
        
        Args:
            material: Material name
        
        Returns:
            Dict with material properties
        """
        if self._available and self.db:
            mat = self.db.get_material(material)
            if mat:
                # Convert MaterialProperties object to dict
                if hasattr(mat, '__dict__'):
                    return {k: v for k, v in mat.__dict__.items() if not k.startswith('_')}
                elif hasattr(mat, '_asdict'):
                    return mat._asdict()
                else:
                    return {'name': material, 'data': str(mat)}
        
        # Return basic info
        return {
            'name': material,
            'refractive_index': self.get_refractive_index(material),
            'abbe_number': 60.0,  # Typical value
            'dispersion_available': False
        }


# Export services
__all__ = [
    'LensService',
    'CalculationService',
    'MaterialDatabaseService'
]
