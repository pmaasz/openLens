#!/usr/bin/env python3
"""
Lens Comparison Tool
Side-by-side comparison of multiple lens designs
"""

from typing import List, Dict, Any
from dataclasses import dataclass

try:
    from .lens_editor import Lens
    from .optical_system import OpticalSystem
    from .performance_metrics import PerformanceMetrics
    from .aberrations import AberrationsCalculator
except (ImportError, ValueError):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from lens_editor import Lens
    from optical_system import OpticalSystem
    from performance_metrics import PerformanceMetrics
    from aberrations import AberrationsCalculator


@dataclass
class ComparisonResult:
    """Results of lens comparison"""
    name: str
    focal_length: float
    f_number: float
    numerical_aperture: float
    spherical_aberration: float
    chromatic_aberration: float
    coma: float
    diameter: float
    thickness: float
    material: str
    airy_disk_radius: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            'name': self.name,
            'focal_length': self.focal_length,
            'f_number': self.f_number,
            'numerical_aperture': self.numerical_aperture,
            'spherical_aberration': self.spherical_aberration,
            'chromatic_aberration': self.chromatic_aberration,
            'coma': self.coma,
            'diameter': self.diameter,
            'thickness': self.thickness,
            'material': self.material,
            'airy_disk_radius': self.airy_disk_radius
        }


class LensComparator:
    """Compare multiple lens designs"""
    
    def __init__(self):
        self.lenses: List[Lens] = []
        self.results: List[ComparisonResult] = []
    
    def add_lens(self, lens: Lens):
        """Add a lens to comparison"""
        self.lenses.append(lens)
    
    def clear(self):
        """Clear all lenses"""
        self.lenses = []
        self.results = []
    
    def compare(self) -> List[ComparisonResult]:
        """Compare all added lenses"""
        self.results = []
        
        for lens in self.lenses:
            # Calculate metrics
            metrics = PerformanceMetrics(lens)
            aberr_calc = AberrationsCalculator(lens)
            
            # Get all aberrations
            aberrations = aberr_calc.calculate_all_aberrations()
            
            # Safely extract aberration values
            spherical_val = 0
            if 'spherical' in aberrations and isinstance(aberrations['spherical'], dict):
                spherical_val = abs(aberrations['spherical'].get('longitudinal', 0))
            
            chromatic_val = 0
            if 'chromatic' in aberrations and isinstance(aberrations['chromatic'], dict):
                chromatic_val = aberrations['chromatic'].get('longitudinal', 0)
            
            coma_val = 0
            if 'coma' in aberrations:
                if isinstance(aberrations['coma'], dict):
                    coma_val = abs(aberrations['coma'].get('tangential', 0))
                elif isinstance(aberrations['coma'], (int, float)):
                    coma_val = abs(aberrations['coma'])
            
            # Create result
            result = ComparisonResult(
                name=lens.name,
                focal_length=lens.calculate_focal_length() or 0,
                f_number=metrics.calculate_f_number() or 0,
                numerical_aperture=metrics.calculate_numerical_aperture() or 0,
                spherical_aberration=spherical_val,
                chromatic_aberration=chromatic_val,
                coma=coma_val,
                diameter=lens.diameter,
                thickness=lens.thickness,
                material=lens.material,
                airy_disk_radius=metrics.calculate_airy_disk_radius() or 0
            )
            
            self.results.append(result)
        
        return self.results
    
    def get_parameter_differences(self) -> Dict[str, Dict[str, float]]:
        """Get differences for each parameter across all lenses"""
        if len(self.results) < 2:
            return {}
        
        diffs = {}
        
        # Compare each numeric parameter
        params = ['focal_length', 'f_number', 'numerical_aperture', 
                 'spherical_aberration', 'chromatic_aberration', 'coma',
                 'diameter', 'thickness', 'airy_disk_radius']
        
        for param in params:
            values = [getattr(r, param) for r in self.results]
            min_val = min(values)
            max_val = max(values)
            
            diffs[param] = {
                'min': min_val,
                'max': max_val,
                'range': max_val - min_val,
                'percent_diff': ((max_val - min_val) / max_val * 100) if max_val != 0 else 0
            }
        
        return diffs
    
    def rank_by_parameter(self, parameter: str, ascending: bool = True) -> List[ComparisonResult]:
        """Rank lenses by a specific parameter"""
        if not self.results:
            return []
        
        return sorted(self.results, 
                     key=lambda r: getattr(r, parameter),
                     reverse=not ascending)
    
    def get_best_overall(self, weights: Dict[str, float] = None) -> ComparisonResult:
        """
        Get best lens based on weighted criteria
        Lower is better for aberrations, higher for NA
        """
        if not self.results:
            return None
        
        if weights is None:
            weights = {
                'spherical_aberration': -1.0,  # Negative = lower is better
                'chromatic_aberration': -1.0,
                'coma': -1.0,
                'numerical_aperture': 1.0,     # Positive = higher is better
                'airy_disk_radius': -1.0
            }
        
        scores = []
        for result in self.results:
            score = 0
            for param, weight in weights.items():
                value = getattr(result, param, 0)
                score += value * weight
            scores.append(score)
        
        best_idx = scores.index(max(scores))
        return self.results[best_idx]
    
    def generate_comparison_table(self) -> str:
        """Generate text table of comparison"""
        if not self.results:
            return "No lenses to compare"
        
        lines = []
        lines.append("="*80)
        lines.append("LENS COMPARISON")
        lines.append("="*80)
        lines.append("")
        
        # Header
        lines.append(f"{'Parameter':<25} " + " ".join(f"{r.name[:12]:>12}" for r in self.results))
        lines.append("-"*80)
        
        # Rows
        params = [
            ('Focal Length (mm)', 'focal_length', '.2f'),
            ('F-number', 'f_number', '.2f'),
            ('Numerical Aperture', 'numerical_aperture', '.4f'),
            ('Diameter (mm)', 'diameter', '.2f'),
            ('Thickness (mm)', 'thickness', '.2f'),
            ('Material', 'material', 's'),
            ('Spherical Aberr (mm)', 'spherical_aberration', '.4f'),
            ('Chromatic Aberr (mm)', 'chromatic_aberration', '.4f'),
            ('Coma (mm)', 'coma', '.4f'),
            ('Airy Disk Radius (µm)', 'airy_disk_radius', '.2f')
        ]
        
        for label, attr, fmt in params:
            values = []
            for r in self.results:
                val = getattr(r, attr)
                if attr == 'airy_disk_radius':
                    val *= 1000  # Convert to µm
                if isinstance(val, str):
                    values.append(f"{val:>12}")
                else:
                    values.append(f"{val:>12{fmt}}")
            
            lines.append(f"{label:<25} " + " ".join(values))
        
        lines.append("="*80)
        
        return "\n".join(lines)
    
    def export_to_csv(self, filename: str):
        """Export comparison to CSV file"""
        import csv
        
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=self.results[0].to_dict().keys())
            writer.writeheader()
            for result in self.results:
                writer.writerow(result.to_dict())
