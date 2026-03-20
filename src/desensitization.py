"""
Desensitization Optimization Module.
Optimizes optical systems for manufacturing yield by minimizing sensitivity to tolerances.
"""

import math
import copy
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

try:
    from .optimizer import LensOptimizer, OptimizationResult, OptimizationVariable, OptimizationTarget, MeritFunction
    from .optical_system import OpticalSystem
    from .tolerancing import ToleranceOperand, ToleranceType, MonteCarloAnalyzer
except (ImportError, ValueError):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from src.optimizer import LensOptimizer, OptimizationResult, OptimizationVariable, OptimizationTarget, MeritFunction
    from src.optical_system import OpticalSystem
    from src.tolerancing import ToleranceOperand, ToleranceType, MonteCarloAnalyzer

class RobustMeritFunction(MeritFunction):
    """
    Wraps a standard MeritFunction to add sensitivity penalties.
    Merit = Nominal_Merit + Weight * Sensitivity
    """
    def __init__(self, system: OpticalSystem, targets: List[OptimizationTarget], 
                 tolerances: List[ToleranceOperand], sensitivity_weight: float = 1.0,
                 constraints: Optional[Dict[str, float]] = None):
        super().__init__(system, targets, constraints)
        self.tolerances = tolerances
        self.sensitivity_weight = sensitivity_weight
        
    def evaluate(self, system: OpticalSystem) -> float:
        # 1. Calculate Nominal Merit
        nominal_merit = super().evaluate(system)
        
        # 2. Calculate Sensitivity (RSS of change in merit)
        # We use a simplified approach: perturb each toleranced parameter by a small amount
        # (e.g. 1 sigma or a fixed fraction of the tolerance range)
        # and measure the change in merit.
        
        sum_sq_diff = 0.0
        
        # To avoid excessive computation, we might only check a subset or use a larger step?
        # For true desensitization, we need to check the local curvature of the merit landscape.
        
        # Let's use a small subset of tolerances or just the variables being optimized?
        # Usually, we care about sensitivity to ALL tolerances, not just the variables.
        # But iterating through 50 tolerances for every merit evaluation is too slow.
        # Strategy: Use a few key tolerances or a random subset?
        # Strategy: Use the "Gaussian Quadrature" method (sample at +/- sigma)
        
        # For this implementation, we will check sensitivity to the OPTIMIZATION VARIABLES
        # assuming they are the ones that drift.
        # Or better, iterate through self.tolerances.
        
        # Limit to first 5 tolerances for performance if list is long?
        # Or just use the first few that match optimization variables?
        
        # Let's try a deterministic approach: Perturb each tolerance by its max value
        # and sum the squared differences.
        
        # Optimization: Reuse the system object?
        # Deepcopy is slow.
        # We can apply perturbation, evaluate, then un-apply.
        
        for tol in self.tolerances:
            # Save original value
            original_val = self._get_param_value(system, tol)
            if original_val is None: continue
            
            # Perturb +
            delta = tol.max_val # Check at the limit
            self._set_param_value(system, tol, original_val + delta)
            
            merit_plus = super().evaluate(system)
            
            # Perturb - (optional, assuming linearity one side might be enough)
            # self._set_param_value(system, tol, original_val - delta)
            # merit_minus = super().evaluate(system)
            
            # Restore
            self._set_param_value(system, tol, original_val)
            
            # Difference
            diff = merit_plus - nominal_merit
            sum_sq_diff += diff * diff
            
        sensitivity = math.sqrt(sum_sq_diff)
        
        return nominal_merit + self.sensitivity_weight * sensitivity

    def _get_param_value(self, system: OpticalSystem, tol: ToleranceOperand) -> Optional[float]:
        # Helper to get value based on tolerance operand
        # Needs to handle the flattened index logic from tolerancing.py
        # This is duplicated logic, ideally should be refactored.
        nodes = system.root.get_flat_list()
        element_nodes = [n for n, _ in nodes if getattr(n, 'is_element', False)]
        
        if tol.element_index >= len(element_nodes): return None
        node = element_nodes[tol.element_index]
        lens = getattr(node, 'element_model', None)
        if not lens: return None
        
        if tol.param_type == ToleranceType.RADIUS_1: return lens.radius_of_curvature_1
        if tol.param_type == ToleranceType.RADIUS_2: return lens.radius_of_curvature_2
        if tol.param_type == ToleranceType.THICKNESS: return lens.thickness
        if tol.param_type == ToleranceType.REFRACTIVE_INDEX: return lens.refractive_index
        return None

    def _set_param_value(self, system: OpticalSystem, tol: ToleranceOperand, value: float):
        nodes = system.root.get_flat_list()
        element_nodes = [n for n, _ in nodes if getattr(n, 'is_element', False)]
        
        if tol.element_index >= len(element_nodes): return
        node = element_nodes[tol.element_index]
        lens = getattr(node, 'element_model', None)
        if not lens: return
        
        if tol.param_type == ToleranceType.RADIUS_1: lens.radius_of_curvature_1 = value
        if tol.param_type == ToleranceType.RADIUS_2: lens.radius_of_curvature_2 = value
        if tol.param_type == ToleranceType.THICKNESS: lens.thickness = value
        if tol.param_type == ToleranceType.REFRACTIVE_INDEX: lens.refractive_index = value
        
        # Important: Update positions if thickness changed
        if tol.param_type == ToleranceType.THICKNESS:
            system._update_positions()

class DesensitizationOptimizer(LensOptimizer):
    """
    Optimizes for Yield.
    """
    def optimize_robust(self, tolerances: List[ToleranceOperand], sensitivity_weight: float = 1.0, 
                       max_iterations: int = 50) -> OptimizationResult:
        """
        Run robust optimization.
        
        Args:
            tolerances: List of tolerances to be insensitive to.
            sensitivity_weight: Weight of sensitivity term in merit function.
            max_iterations: Max iterations.
            
        Returns:
            OptimizationResult.
        """
        # Replace default merit function with RobustMeritFunction
        original_merit_function = self.merit_function
        
        # Preserve constraints if they exist
        constraints = getattr(original_merit_function, 'constraints', None)
        
        self.merit_function = RobustMeritFunction(
            self.system, 
            self.targets, 
            tolerances, 
            sensitivity_weight,
            constraints=constraints
        )
        
        # Run simplex
        result = self.optimize_simplex(max_iterations=max_iterations)
        
        # Restore merit function
        self.merit_function = original_merit_function
        
        return result
