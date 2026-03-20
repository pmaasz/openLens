from typing import List, Tuple, Dict, Any, Optional
import math

try:
    from ..vector3 import Vector3, vec3
    from ..ray_tracer import Ray3D, SystemRayTracer3D
    from ..optical_system import OpticalSystem
    from ..constants import NM_TO_MM, WAVELENGTH_GREEN
except ImportError:
    from src.vector3 import Vector3, vec3
    from src.ray_tracer import Ray3D, SystemRayTracer3D
    from src.optical_system import OpticalSystem
    from src.constants import NM_TO_MM, WAVELENGTH_GREEN

class GeometricTraceAnalysis:
    """
    Geometric analysis tools using real ray tracing for the full Optical System.
    Includes Ray Fan, Field Curvature, and Distortion analysis.
    """
    
    def __init__(self, system: OpticalSystem):
        self.system = system
        self.tracer = SystemRayTracer3D(system)

    def _linspace(self, start: float, stop: float, num: int) -> List[float]:
        if num <= 1:
            return [start]
        step = (stop - start) / (num - 1)
        return [start + i * step for i in range(num)]

    def _get_image_plane_x(self, wavelength: float = WAVELENGTH_GREEN) -> float:
        """
        Determine the image plane position (paraxial focus) for the system.
        """
        # Save state
        original_states = []
        for element in self.system.elements:
            lens = element.lens
            original_states.append((lens, lens.wavelength))
            lens.update_refractive_index(wavelength=wavelength)
            
        try:
            # Trace paraxial ray
            start_x = self.system.elements[0].position - 10.0
            para_ray = Ray3D(vec3(start_x, 0.001, 0), vec3(1, 0, 0), wavelength=wavelength * NM_TO_MM)
            self.tracer.trace_ray(para_ray)
            
            if len(para_ray.path) >= 2:
                p2 = para_ray.path[-1]
                p1 = para_ray.path[-2]
                dx = p2.x - p1.x
                dy = p2.y - p1.y
                if abs(dy) > 1e-9:
                    slope = dy/dx
                    x_focus = p1.x - p1.y / slope
                    return x_focus
            
            return self.system.get_total_length() + 10.0
            
        finally:
            # Restore state
            for lens, wl in original_states:
                lens.wavelength = wl
                lens.update_refractive_index(wavelength=wl)

    def calculate_ray_fan(self, 
                          field_angle: float = 0.0, 
                          wavelength: float = WAVELENGTH_GREEN,
                          num_points: int = 21,
                          pupil_axis: str = 'y') -> Dict[str, Any]:
        """
        Calculate Ray Fan (Transverse Ray Aberration).
        
        Args:
            field_angle: Field angle in degrees.
            wavelength: Wavelength in nm.
            num_points: Number of points across the pupil diameter.
            pupil_axis: 'y' for Tangential (Meridional) fan, 'z' for Sagittal fan.
            
        Returns:
            Dictionary with 'pupil_coords' (normalized -1 to 1) and 'ray_errors' (mm).
        """
        wl_mm = wavelength * NM_TO_MM
        image_plane_x = self._get_image_plane_x(wavelength)
        
        # Entrance Pupil Diameter (approximate as first lens diameter)
        ep_diam = self.system.elements[0].lens.diameter if self.system.elements else 1.0
        max_r = ep_diam / 2.0
        
        # Ray direction based on field angle (Tangential plane tilt)
        tan_theta = math.tan(math.radians(field_angle))
        direction = vec3(1.0, tan_theta, 0.0).normalize()
        
        # Determine Chief Ray intersection (reference point)
        start_x = self.system.elements[0].position - 50.0
        # Chief ray passes through center of pupil (approx first surface center)
        first_surface_x = self.system.elements[0].position
        
        # Back propagate to start
        t_chief = (first_surface_x - start_x) / direction.x
        chief_ray_origin = vec3(first_surface_x, 0, 0) - direction * t_chief
        
        chief_ray = Ray3D(chief_ray_origin, direction, wavelength=wl_mm)
        self.tracer.trace_ray(chief_ray)
        
        ref_y = 0.0
        ref_z = 0.0
        
        if not chief_ray.terminated and abs(chief_ray.direction.x) > 1e-6:
             t = (image_plane_x - chief_ray.origin.x) / chief_ray.direction.x
             ref_y = chief_ray.origin.y + t * chief_ray.direction.y
             ref_z = chief_ray.origin.z + t * chief_ray.direction.z
        
        pupil_coords = self._linspace(-1.0, 1.0, num_points)
        ray_errors = []
        valid_coords = []
        
        for p in pupil_coords:
            r_offset = p * max_r
            
            if pupil_axis == 'y':
                offset_vec = vec3(0, r_offset, 0)
            else:
                offset_vec = vec3(0, 0, r_offset)
                
            # Launch point at first lens plane
            launch_point = vec3(first_surface_x, 0, 0) + offset_vec
            
            # Back propagate to start_x
            dist = first_surface_x - start_x
            t = dist / direction.x
            origin = launch_point - direction * t
            
            ray = Ray3D(origin, direction, wavelength=wl_mm)
            self.tracer.trace_ray(ray)
            
            error = float('nan')
            if not ray.terminated and abs(ray.direction.x) > 1e-6:
                t = (image_plane_x - ray.origin.x) / ray.direction.x
                img_y = ray.origin.y + t * ray.direction.y
                img_z = ray.origin.z + t * ray.direction.z
                
                if pupil_axis == 'y':
                    # Transverse error in Y (Tangential)
                    error = img_y - ref_y
                else:
                    # Sagittal ray fan error in X (sagittal direction)
                    # If plotting vs Py (pupil Y), we look at error in X?
                    # No, usually sagittal fan is plotted vs pupil X (sagittal pupil axis).
                    # Here pupil_axis='z' means we vary pupil coordinate along Z (sagittal).
                    # So we should look at error in Z.
                    error = img_z - ref_z 
            
            if not math.isnan(error):
                valid_coords.append(p)
                ray_errors.append(error)
                
        return {
            'pupil_coords': valid_coords,
            'ray_errors': ray_errors,
            'axis': pupil_axis,
            'field_angle': field_angle,
            'wavelength': wavelength
        }

    def calculate_field_curvature_distortion(self, 
                                           max_field_angle: float = 20.0, 
                                           num_points: int = 11,
                                           wavelength: float = WAVELENGTH_GREEN) -> Dict[str, Any]:
        """
        Calculate Field Curvature and Distortion.
        
        Args:
            max_field_angle: Maximum semi-field angle in degrees.
            num_points: Number of field points to sample.
            wavelength: Wavelength in nm.
            
        Returns:
            Dictionary with arrays for field angles, tangential/sagittal focus shift, and distortion %.
        """
        wl_mm = wavelength * NM_TO_MM
        image_plane_x = self._get_image_plane_x(wavelength)
        
        angles = self._linspace(0, max_field_angle, num_points)
        
        tan_focus_shifts = []
        sag_focus_shifts = []
        distortion_pcts = []
        
        ep_diam = self.system.elements[0].lens.diameter if self.system.elements else 1.0
        delta = ep_diam * 0.01 
        
        start_x = self.system.elements[0].position - 50.0
        
        for angle in angles:
            tan_theta = math.tan(math.radians(angle))
            direction_principal = vec3(1.0, tan_theta, 0.0).normalize()
            
            # 1. Trace Chief Ray
            first_lens_x = self.system.elements[0].position
            t_principal = (first_lens_x - start_x) / direction_principal.x
            origin_principal = vec3(first_lens_x, 0, 0) - direction_principal * t_principal
            
            chief_ray = Ray3D(origin_principal, direction_principal, wavelength=wl_mm)
            self.tracer.trace_ray(chief_ray)
            
            if chief_ray.terminated:
                tan_focus_shifts.append(float('nan'))
                sag_focus_shifts.append(float('nan'))
                distortion_pcts.append(float('nan'))
                continue
                
            # Intersect with paraxial image plane
            t_img = (image_plane_x - chief_ray.origin.x) / chief_ray.direction.x
            real_image_height = chief_ray.origin.y + t_img * chief_ray.direction.y
            
            # Paraxial image height (h = f * tan(theta))
            efl = self.system.get_system_focal_length() or 100.0
            paraxial_height = efl * tan_theta
            
            distortion = 0.0
            if abs(paraxial_height) > 1e-6:
                distortion = 100.0 * (real_image_height - paraxial_height) / paraxial_height
            elif abs(angle) < 1e-6:
                distortion = 0.0
            else:
                distortion = 0.0 
                
            distortion_pcts.append(distortion)
            
            # 2. Tangential Focus
            offset_y = delta
            launch_pt_tan = vec3(first_lens_x, offset_y, 0)
            t_tan = (first_lens_x - start_x) / direction_principal.x
            origin_tan = launch_pt_tan - direction_principal * t_tan
            
            ray_tan = Ray3D(origin_tan, direction_principal, wavelength=wl_mm)
            self.tracer.trace_ray(ray_tan)
            
            if not ray_tan.terminated:
                m1 = ray_tan.direction.y / ray_tan.direction.x
                m2 = chief_ray.direction.y / chief_ray.direction.x
                
                if abs(m2 - m1) > 1e-9:
                    x_tan_focus = (ray_tan.origin.y - chief_ray.origin.y - ray_tan.origin.x*m1 + chief_ray.origin.x*m2) / (m2 - m1)
                    tan_focus_shifts.append(x_tan_focus - image_plane_x)
                else:
                    tan_focus_shifts.append(0.0) 
            else:
                tan_focus_shifts.append(float('nan'))

            # 3. Sagittal Focus
            offset_z = delta
            launch_pt_sag = vec3(first_lens_x, 0, offset_z)
            t_sag = (first_lens_x - start_x) / direction_principal.x
            origin_sag = launch_pt_sag - direction_principal * t_sag
            
            ray_sag = Ray3D(origin_sag, direction_principal, wavelength=wl_mm)
            self.tracer.trace_ray(ray_sag)
            
            if not ray_sag.terminated:
                if abs(ray_sag.direction.z) > 1e-9:
                    u = -ray_sag.origin.z / ray_sag.direction.z
                    x_sag_focus = ray_sag.origin.x + u * ray_sag.direction.x
                    sag_focus_shifts.append(x_sag_focus - image_plane_x)
                else:
                    sag_focus_shifts.append(0.0)
            else:
                sag_focus_shifts.append(float('nan'))
                
        return {
            'field_angles': angles,
            'tan_focus_shift': tan_focus_shifts,
            'sag_focus_shift': sag_focus_shifts,
            'distortion_pct': distortion_pcts,
            'image_plane_x': image_plane_x
        }
