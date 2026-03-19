
import enum
import random
import copy
import math
import statistics
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple

try:
    from .optical_system import OpticalSystem
    from .optical_node import OpticalElement
    from .analysis import SpotDiagram
    from .vector3 import vec3
except ImportError:
    from optical_system import OpticalSystem
    from optical_node import OpticalElement
    from analysis import SpotDiagram
    from vector3 import vec3

class ToleranceType(enum.Enum):
    RADIUS_1 = "Radius 1"
    RADIUS_2 = "Radius 2"
    THICKNESS = "Thickness"
    REFRACTIVE_INDEX = "Refractive Index"
    DECENTER_X = "Decenter X"
    DECENTER_Y = "Decenter Y"
    TILT_X = "Tilt X"
    TILT_Y = "Tilt Y"
    AIR_GAP = "Air Gap"

@dataclass
class ToleranceOperand:
    """
    Defines a tolerance on a specific parameter of an element.
    """
    element_index: int  # Index in the flattened element list (0-based)
    param_type: ToleranceType
    min_val: float      # Minimum deviation (e.g. -0.1 mm)
    max_val: float      # Maximum deviation (e.g. +0.1 mm)
    distribution: str = "uniform"  # "uniform" or "gaussian"
    std_dev: float = 0.0  # Standard deviation for Gaussian (if 0, assumes sigma is roughly (max-min)/6 ?)

    def generate_value(self) -> float:
        """Generate a random deviation value based on distribution."""
        if self.distribution == "gaussian":
            # If std_dev is not provided, assume range is +/- 3 sigma
            sigma = self.std_dev
            if sigma == 0:
                sigma = (self.max_val - self.min_val) / 6.0
            
            val = random.gauss(0, sigma)
            # Clamp to limits? Typically yes for manufacturing
            return max(self.min_val, min(self.max_val, val))
        else:
            # Uniform
            return random.uniform(self.min_val, self.max_val)

class MonteCarloAnalyzer:
    """
    Performs Monte Carlo analysis to estimate production yield.
    """
    def __init__(self, system: OpticalSystem, tolerances: List[ToleranceOperand]):
        self.nominal_system = system
        self.tolerances = tolerances
        self.results: List[Dict[str, Any]] = []
        
    def _apply_tolerances(self, system: OpticalSystem) -> Dict[str, float]:
        """
        Apply random tolerances to the system and return the applied values.
        """
        perturbations = {}
        
        # Get flat list of nodes for mapping indices to objects
        nodes = system.root.get_flat_list()
        element_nodes = [n for n, _ in nodes if getattr(n, 'is_element', False)]
        
        for tol in self.tolerances:
            delta = tol.generate_value()
            perturbations[f"El_{tol.element_index}_{tol.param_type.name}"] = delta
            
            if tol.element_index >= len(element_nodes):
                continue
                
            node = element_nodes[tol.element_index]
            lens = getattr(node, 'element_model', None)
            
            if not lens:
                continue
            
            if tol.param_type == ToleranceType.RADIUS_1:
                lens.radius_of_curvature_1 += delta
            elif tol.param_type == ToleranceType.RADIUS_2:
                lens.radius_of_curvature_2 += delta
            elif tol.param_type == ToleranceType.THICKNESS:
                lens.thickness += delta
            elif tol.param_type == ToleranceType.REFRACTIVE_INDEX:
                lens.refractive_index += delta
            elif tol.param_type == ToleranceType.DECENTER_Y:
                node.position.y += delta
            elif tol.param_type == ToleranceType.TILT_X:
                node.rotation.x += delta
            # TODO: Handle other types like AIR_GAP (requires modifying gaps list or adjacent node positions)

            # Update system positions after thickness changes
        # Note: _update_positions() in OpticalSystem syncs flat list positions from tree or vice versa?
        # In our current hybrid model:
        # OpticalSystem._update_positions calculates positions based on flat list THICKNESSES.
        # But if we modify node.position directly (Decenter), that's local offset.
        # The flat list 'position' is axial (Z/X).
        # We need to be careful.
        
        # If we modified lens thickness, we need to propagate axial shifts.
        system._update_positions()
        
        return perturbations

    def run(self, num_trials: int = 100, 
            criterion: str = 'rms_spot_radius', 
            criterion_limit: float = 0.05) -> Dict[str, Any]:
        """
        Run Monte Carlo simulation.
        
        Args:
            num_trials: Number of systems to simulate.
            criterion: Metric to evaluate ('rms_spot_radius').
            criterion_limit: Pass/Fail threshold.
            
        Returns:
            Dictionary with statistics and yield.
        """
        self.results = []
        pass_count = 0
        
        # Analyze nominal system first
        spot_nom = SpotDiagram(self.nominal_system)
        res_nom = spot_nom.trace_spot()
        nominal_val = res_nom['rms_radius']
        
        for i in range(num_trials):
            # Deep copy the system
            # Note: deepcopying complex objects can be tricky.
            # OpticalSystem -> Elements -> Lens
            # Let's try standard deepcopy.
            perturbed_system = copy.deepcopy(self.nominal_system)
            
            # Apply tolerances
            perturbations = self._apply_tolerances(perturbed_system)
            
            # Analyze
            spot = SpotDiagram(perturbed_system)
            # Use same settings as nominal (e.g., image plane might shift if we allow compensators)
            # For now, assume fixed image plane or paraxial focus?
            # Standard MC allows a compensator (usually back focal distance).
            # SpotDiagram.trace_spot() automatically finds best focus if image_plane_x is None.
            # This acts as a compensator.
            results = spot.trace_spot()
            
            val = results['rms_radius']
            passed = val <= criterion_limit
            if passed:
                pass_count += 1
                
            self.results.append({
                'trial': i,
                'perturbations': perturbations,
                'value': val,
                'passed': passed
            })
            
        # Statistics
        values = [r['value'] for r in self.results]
        yield_pct = (pass_count / num_trials) * 100
        
        stats = {
            'nominal': nominal_val,
            'mean': statistics.mean(values) if values else 0,
            'std_dev': statistics.stdev(values) if len(values) > 1 else 0,
            'min': min(values) if values else 0,
            'max': max(values) if values else 0,
            'yield': yield_pct,
            'trials': num_trials,
            'criterion': criterion,
            'limit': criterion_limit,
            '90th_percentile': sorted(values)[int(0.9 * len(values))] if values else 0
        }
        
        return stats


class InverseSensitivityAnalyzer:
    """
    Calculates required tolerances to achieve a target performance.
    """
    def __init__(self, system: OpticalSystem, tolerances: List[ToleranceOperand]):
        self.system = system
        self.tolerances = tolerances

    def calculate_sensitivities(self, criterion: str = 'rms_spot_radius') -> List[Dict[str, Any]]:
        """
        Calculate sensitivity of each operand.
        Returns list of dicts with 'operand', 'sensitivity', 'change'.
        """
        results = []
        
        # Nominal performance
        spot_nom = SpotDiagram(self.system)
        res_nom = spot_nom.trace_spot()
        nominal_val = res_nom['rms_radius']
        
        for i, tol in enumerate(self.tolerances):
            # Test at max value
            # We use a simplified version of apply_tolerances that only applies ONE tolerance
            perturbed_system = copy.deepcopy(self.system)
            
            # Apply single tolerance at max value
            delta = tol.max_val
            self._apply_single_tolerance(perturbed_system, tol, delta)
            
            # Analyze
            spot = SpotDiagram(perturbed_system)
            res = spot.trace_spot()
            val = res['rms_radius']
            
            change = val - nominal_val
            # Sensitivity = change / tolerance_value
            sensitivity = change / delta if delta != 0 else 0
            
            results.append({
                'operand_index': i,
                'type': tol.param_type.name,
                'element': tol.element_index,
                'test_value': delta,
                'result_value': val,
                'change': change,
                'sensitivity': sensitivity
            })
            
        return results

    def _apply_single_tolerance(self, system: OpticalSystem, tol: ToleranceOperand, value: float):
        """Helper to apply a single tolerance value."""
        nodes = system.root.get_flat_list()
        element_nodes = [n for n, _ in nodes if getattr(n, 'is_element', False)]
        
        if tol.element_index >= len(element_nodes):
            return
            
        node = element_nodes[tol.element_index]
        lens = getattr(node, 'element_model', None)
        
        if not lens:
            return
            
        if tol.param_type == ToleranceType.RADIUS_1:
            lens.radius_of_curvature_1 += value
        elif tol.param_type == ToleranceType.RADIUS_2:
            lens.radius_of_curvature_2 += value
        elif tol.param_type == ToleranceType.THICKNESS:
            lens.thickness += value
        elif tol.param_type == ToleranceType.REFRACTIVE_INDEX:
            lens.refractive_index += value
        elif tol.param_type == ToleranceType.DECENTER_Y:
            node.position.y += value
        elif tol.param_type == ToleranceType.TILT_X:
            node.rotation.x += value
            
        system._update_positions()

    def optimize_limits(self, target_yield_criterion: float, method: str = 'rss') -> List[ToleranceOperand]:
        """
        Calculate new tolerance limits to meet a target performance degradation budget.
        
        Args:
            target_yield_criterion: The allowed degradation from nominal (e.g. +0.01 rms spot).
            method: 'rss' (Root Sum Square) or 'worst_case' (Linear Sum).
            
        Returns:
            List of new ToleranceOperand with updated min/max.
        """
        sensitivities = self.calculate_sensitivities()
        new_tolerances = []
        
        num_vars = len(self.tolerances)
        if num_vars == 0:
            return []
            
        # Allocate budget per operand
        if method == 'rss':
            # Budget per operand = Total / sqrt(N)
            # This assumes all operands contribute equally to the variance
            budget_per_op = target_yield_criterion / math.sqrt(num_vars)
        else:
            # Worst case: Budget / N
            budget_per_op = target_yield_criterion / num_vars
            
        for i, sens_data in enumerate(sensitivities):
            original_tol = self.tolerances[i]
            s = abs(sens_data['sensitivity'])
            
            if s < 1e-9:
                # Insensitive parameter, keep original or even loosen?
                # For safety, keep original.
                new_limit = original_tol.max_val
            else:
                # Limit = Budget / Sensitivity
                new_limit = budget_per_op / s
            
            # Create new operand
            new_tol = copy.deepcopy(original_tol)
            new_tol.max_val = new_limit
            new_tol.min_val = -new_limit  # Assuming symmetric tolerances for simplicity
            
            new_tolerances.append(new_tol)
            
        return new_tolerances

def generate_yield_report(stats: Dict[str, Any]) -> str:
    """Generate a text report from Monte Carlo stats."""
    lines = []
    lines.append("=== Monte Carlo Yield Analysis ===")
    lines.append(f"Criterion: {stats['criterion']}")
    lines.append(f"Pass/Fail Limit: {stats['limit']}")
    lines.append(f"Number of Trials: {stats['trials']}")
    lines.append("-" * 30)
    lines.append(f"Nominal Performance: {stats['nominal']:.4f}")
    lines.append(f"Mean Performance:    {stats['mean']:.4f}")
    lines.append(f"Std Dev:             {stats['std_dev']:.4f}")
    lines.append(f"90th Percentile:     {stats['90th_percentile']:.4f}")
    lines.append(f"Worst Case (Max):    {stats['max']:.4f}")
    lines.append("-" * 30)
    lines.append(f"ESTIMATED YIELD:     {stats['yield']:.1f}%")
    lines.append("==================================")
    return "\n".join(lines)

