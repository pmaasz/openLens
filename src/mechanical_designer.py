"""
Mechanical Design Module
Handles lens housing, mounting, and spacing calculations.
"""

import numpy as np
from typing import List, Dict, Tuple, Optional, Any
from dataclasses import dataclass


@dataclass
class LensMount:
    """Lens mounting specifications."""
    lens_diameter: float  # mm
    mount_type: str  # 'C-mount', 'M42', 'custom', etc.
    thread_diameter: float  # mm
    thread_pitch: float  # mm
    flange_distance: float  # mm
    clear_aperture: float  # mm
    
    def get_specifications(self) -> Dict[str, Any]:
        """Get mount specifications."""
        return {
            'lens_diameter': self.lens_diameter,
            'mount_type': self.mount_type,
            'thread_diameter': self.thread_diameter,
            'thread_pitch': self.thread_pitch,
            'flange_distance': self.flange_distance,
            'clear_aperture': self.clear_aperture
        }


@dataclass
class LensCell:
    """Lens cell (housing) design."""
    inner_diameter: float  # mm
    outer_diameter: float  # mm
    length: float  # mm
    wall_thickness: float  # mm
    material: str  # 'aluminum', 'brass', 'plastic', etc.
    threads_external: bool
    threads_internal: bool
    
    def calculate_weight(self) -> float:
        """Calculate cell weight in grams."""
        # Material densities (g/cm³)
        densities = {
            'aluminum': 2.7,
            'brass': 8.5,
            'plastic': 1.2,
            'titanium': 4.5,
            'steel': 7.8
        }
        
        density = densities.get(self.material.lower(), 2.7)
        
        # Volume calculation
        outer_volume = np.pi * (self.outer_diameter/2)**2 * self.length
        inner_volume = np.pi * (self.inner_diameter/2)**2 * self.length
        volume_mm3 = outer_volume - inner_volume
        volume_cm3 = volume_mm3 / 1000
        
        return volume_cm3 * density


@dataclass
class Spacer:
    """Lens spacing element."""
    thickness: float  # mm
    inner_diameter: float  # mm
    outer_diameter: float  # mm
    material: str
    tolerance: float  # mm
    
    def __repr__(self):
        return f"Spacer({self.thickness:.3f}mm, {self.material})"


class MechanicalDesigner:
    """Design mechanical components for optical systems."""
    
    # Standard mount specifications
    STANDARD_MOUNTS = {
        'C-mount': {
            'thread_diameter': 25.4,
            'thread_pitch': 0.794,  # 32 TPI
            'flange_distance': 17.526
        },
        'CS-mount': {
            'thread_diameter': 25.4,
            'thread_pitch': 0.794,
            'flange_distance': 12.526
        },
        'M42': {
            'thread_diameter': 42.0,
            'thread_pitch': 1.0,
            'flange_distance': 45.46
        },
        'M39': {
            'thread_diameter': 39.0,
            'thread_pitch': 1.0,
            'flange_distance': 28.8
        },
        'T-mount': {
            'thread_diameter': 42.0,
            'thread_pitch': 0.75,
            'flange_distance': 55.0
        }
    }
    
    def __init__(self, optical_system):
        self.optical_system = optical_system
        self.lens_cells: List[LensCell] = []
        self.spacers: List[Spacer] = []
        self.mounts: List[LensMount] = []
        
    def design_lens_cells(self, wall_thickness: float = 2.0,
                         material: str = 'aluminum') -> List[LensCell]:
        """Design lens cells for all elements in the system."""
        self.lens_cells.clear()
        
        if not hasattr(self.optical_system, 'lenses'):
            return []
        
        for lens in self.optical_system.lenses:
            # Get lens diameter
            if hasattr(lens, 'diameter'):
                lens_diameter = lens.diameter
            else:
                lens_diameter = 25.4  # Default 1 inch
            
            # Design cell
            inner_diameter = lens_diameter + 0.1  # Clearance
            outer_diameter = inner_diameter + 2 * wall_thickness
            
            # Estimate length (depends on edge thickness)
            if hasattr(lens, 'center_thickness'):
                length = lens.center_thickness + 5.0  # Add margin
            else:
                length = 10.0
            
            cell = LensCell(
                inner_diameter=inner_diameter,
                outer_diameter=outer_diameter,
                length=length,
                wall_thickness=wall_thickness,
                material=material,
                threads_external=True,
                threads_internal=True
            )
            
            self.lens_cells.append(cell)
        
        return self.lens_cells
    
    def calculate_spacers(self, target_spacing: Optional[List[float]] = None,
                         tolerance: float = 0.1) -> List[Spacer]:
        """Calculate required spacers between lens elements."""
        self.spacers.clear()
        
        if not hasattr(self.optical_system, 'lenses'):
            return []
        
        num_lenses = len(self.optical_system.lenses)
        
        if target_spacing is None:
            # Use default spacing from optical design
            if hasattr(self.optical_system, 'element_spacing'):
                target_spacing = self.optical_system.element_spacing
            else:
                target_spacing = [10.0] * (num_lenses - 1)
        
        for i, spacing in enumerate(target_spacing):
            # Determine spacer dimensions
            if i < len(self.lens_cells):
                inner_dia = self.lens_cells[i].inner_diameter - 2.0
                outer_dia = self.lens_cells[i].outer_diameter
            else:
                inner_dia = 20.0
                outer_dia = 30.0
            
            spacer = Spacer(
                thickness=spacing,
                inner_diameter=inner_dia,
                outer_diameter=outer_dia,
                material='aluminum',
                tolerance=tolerance
            )
            
            self.spacers.append(spacer)
        
        return self.spacers
    
    def design_mount(self, mount_type: str = 'C-mount',
                    lens_diameter: Optional[float] = None) -> LensMount:
        """Design lens mount interface."""
        if mount_type not in self.STANDARD_MOUNTS:
            raise ValueError(f"Unknown mount type: {mount_type}")
        
        specs = self.STANDARD_MOUNTS[mount_type]
        
        if lens_diameter is None:
            if self.lens_cells:
                lens_diameter = self.lens_cells[0].outer_diameter
            else:
                lens_diameter = 25.4
        
        mount = LensMount(
            lens_diameter=lens_diameter,
            mount_type=mount_type,
            thread_diameter=specs['thread_diameter'],
            thread_pitch=specs['thread_pitch'],
            flange_distance=specs['flange_distance'],
            clear_aperture=lens_diameter * 0.8
        )
        
        self.mounts.append(mount)
        return mount
    
    def calculate_total_length(self) -> float:
        """Calculate total mechanical length of assembly."""
        total = 0.0
        
        for cell in self.lens_cells:
            total += cell.length
        
        for spacer in self.spacers:
            total += spacer.thickness
        
        return total
    
    def calculate_total_weight(self) -> float:
        """Calculate total weight of mechanical assembly in grams."""
        total = 0.0
        
        for cell in self.lens_cells:
            total += cell.calculate_weight()
        
        # Spacer weights (simplified)
        for spacer in self.spacers:
            volume_cm3 = (np.pi * ((spacer.outer_diameter/2)**2 - 
                         (spacer.inner_diameter/2)**2) * spacer.thickness) / 1000
            total += volume_cm3 * 2.7  # Aluminum density
        
        return total
    
    def generate_bom(self) -> List[Dict[str, Any]]:
        """Generate Bill of Materials."""
        bom = []
        
        # Lens cells
        for i, cell in enumerate(self.lens_cells):
            bom.append({
                'item': f'Lens Cell {i+1}',
                'part_number': f'LC-{i+1:02d}',
                'description': f'Lens housing, {cell.material}',
                'quantity': 1,
                'dimensions': f'OD={cell.outer_diameter:.1f}mm, L={cell.length:.1f}mm',
                'weight_g': cell.calculate_weight(),
                'material': cell.material
            })
        
        # Spacers
        for i, spacer in enumerate(self.spacers):
            bom.append({
                'item': f'Spacer {i+1}',
                'part_number': f'SP-{i+1:02d}',
                'description': f'Spacing ring, {spacer.material}',
                'quantity': 1,
                'dimensions': f't={spacer.thickness:.2f}mm ±{spacer.tolerance:.2f}mm',
                'weight_g': 0.0,  # Calculated separately
                'material': spacer.material
            })
        
        # Mounts
        for i, mount in enumerate(self.mounts):
            bom.append({
                'item': f'Mount Adapter {i+1}',
                'part_number': f'MT-{i+1:02d}',
                'description': f'{mount.mount_type} adapter',
                'quantity': 1,
                'dimensions': f'Thread={mount.thread_diameter:.1f}mm',
                'weight_g': 0.0,
                'material': 'aluminum'
            })
        
        return bom
    
    def generate_assembly_instructions(self) -> List[str]:
        """Generate assembly instructions."""
        instructions = []
        instructions.append("Lens Assembly Instructions")
        instructions.append("=" * 50)
        instructions.append("")
        
        instructions.append("Required Tools:")
        instructions.append("- Lens spanner wrench")
        instructions.append("- Torque driver (2-5 Nm)")
        instructions.append("- Lint-free gloves")
        instructions.append("- Lens tissue")
        instructions.append("")
        
        instructions.append("Assembly Steps:")
        
        step = 1
        for i, cell in enumerate(self.lens_cells):
            instructions.append(f"{step}. Install Lens {i+1} into Cell {i+1}")
            instructions.append(f"   - Clean lens surfaces")
            instructions.append(f"   - Insert lens into cell")
            instructions.append(f"   - Secure with retaining ring")
            instructions.append("")
            step += 1
            
            if i < len(self.spacers):
                instructions.append(f"{step}. Add Spacer {i+1} ({self.spacers[i].thickness:.2f}mm)")
                instructions.append(f"   - Verify spacer thickness with calipers")
                instructions.append(f"   - Thread onto previous cell")
                instructions.append("")
                step += 1
        
        if self.mounts:
            instructions.append(f"{step}. Attach mount adapter")
            instructions.append(f"   - Thread {self.mounts[0].mount_type} adapter")
            instructions.append(f"   - Torque to specification")
            instructions.append("")
        
        instructions.append("Quality Checks:")
        instructions.append("- Verify all threads engaged properly")
        instructions.append("- Check lens alignment")
        instructions.append("- Test mechanical focus")
        instructions.append("- Inspect for dust/contamination")
        
        return instructions
    
    def export_cad_parameters(self) -> Dict[str, Any]:
        """Export parameters for CAD modeling."""
        return {
            'lens_cells': [
                {
                    'id': i,
                    'inner_diameter': cell.inner_diameter,
                    'outer_diameter': cell.outer_diameter,
                    'length': cell.length,
                    'wall_thickness': cell.wall_thickness,
                    'material': cell.material
                }
                for i, cell in enumerate(self.lens_cells)
            ],
            'spacers': [
                {
                    'id': i,
                    'thickness': spacer.thickness,
                    'inner_diameter': spacer.inner_diameter,
                    'outer_diameter': spacer.outer_diameter,
                    'tolerance': spacer.tolerance
                }
                for i, spacer in enumerate(self.spacers)
            ],
            'total_length': self.calculate_total_length(),
            'total_weight': self.calculate_total_weight()
        }
    
    def check_clearances(self) -> List[Dict[str, Any]]:
        """Check mechanical clearances and interferences."""
        issues = []
        
        # Check lens cells fit together
        for i in range(len(self.lens_cells) - 1):
            cell1 = self.lens_cells[i]
            cell2 = self.lens_cells[i + 1]
            
            # Check if threads are compatible
            if cell1.threads_external and cell2.threads_internal:
                # Should be compatible
                pass
            else:
                issues.append({
                    'type': 'threading',
                    'location': f'Between Cell {i+1} and Cell {i+2}',
                    'message': 'Threading mismatch'
                })
        
        # Check spacer fit
        for i, spacer in enumerate(self.spacers):
            if i < len(self.lens_cells):
                cell = self.lens_cells[i]
                if spacer.outer_diameter > cell.outer_diameter:
                    issues.append({
                        'type': 'clearance',
                        'location': f'Spacer {i+1}',
                        'message': f'Spacer OD exceeds cell OD'
                    })
        
        return issues
