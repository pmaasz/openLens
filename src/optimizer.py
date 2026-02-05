#!/usr/bin/env python3
"""
Optical System Optimization Engine
Automatically optimize lens parameters to minimize aberrations and improve performance
"""

import math
import random
from typing import List, Dict, Tuple, Callable, Optional
from dataclasses import dataclass, field
import copy

try:
    from .lens_editor import Lens
    from .optical_system import OpticalSystem
    from .aberrations import AberrationsCalculator
except (ImportError, ValueError):
    import sys
    import os
    sys.path.insert(0, os.path.dirname(__file__))
    from lens_editor import Lens
    from optical_system import OpticalSystem
    from aberrations import AberrationsCalculator


@dataclass
class OptimizationVariable:
    """A variable that can be optimized"""
    name: str
    element_index: int  # Which lens element (0-based)
    parameter: str  # 'radius_of_curvature_1', 'radius_of_curvature_2', 'thickness', 'air_gap', etc.
    current_value: float
    min_value: float
    max_value: float
    step_size: float = 1.0  # Initial step size for optimization
    
    def is_valid(self, value: float) -> bool:
        """Check if value is within bounds"""
        return self.min_value <= value <= self.max_value
    
    def clamp(self, value: float) -> float:
        """Clamp value to bounds"""
        return max(self.min_value, min(self.max_value, value))


@dataclass
class OptimizationTarget:
    """An optimization target/constraint"""
    name: str
    target_value: float
    weight: float = 1.0  # Importance weight in merit function
    target_type: str = "minimize"  # "minimize", "maximize", "target"


@dataclass
class OptimizationResult:
    """Result of optimization"""
    success: bool
    iterations: int
    initial_merit: float
    final_merit: float
    improvement: float
    optimized_system: OpticalSystem
    variable_history: List[Dict[str, float]] = field(default_factory=list)
    merit_history: List[float] = field(default_factory=list)
    message: str = ""


class MeritFunction:
    """Calculate merit function for optical system quality"""
    
    def __init__(self, system: OpticalSystem, targets: List[OptimizationTarget]):
        self.system = system
        self.targets = targets
    
    def evaluate(self, system: OpticalSystem) -> float:
        """
        Evaluate merit function (lower is better)
        
        Merit function combines multiple targets:
        - Spherical aberration
        - Chromatic aberration
        - Coma
        - Astigmatism
        - Focal length target
        - RMS spot size
        """
        merit = 0.0
        
        for target in self.targets:
            if target.name == "spherical_aberration":
                # Get spherical aberration for first lens
                if system.elements:
                    calc = AberrationsCalculator(system.elements[0].lens)
                    aberr = calc.calculate_spherical_aberration()
                    value = abs(aberr['longitudinal'])
                    
                    if target.target_type == "minimize":
                        merit += target.weight * value
                    elif target.target_type == "target":
                        merit += target.weight * (value - target.target_value)**2
            
            elif target.name == "chromatic_aberration":
                chrom = system.calculate_chromatic_aberration()
                value = chrom['longitudinal']
                
                if target.target_type == "minimize":
                    merit += target.weight * value
                elif target.target_type == "target":
                    merit += target.weight * (value - target.target_value)**2
            
            elif target.name == "focal_length":
                f = system.get_system_focal_length()
                if f:
                    if target.target_type == "target":
                        merit += target.weight * (f - target.target_value)**2
                    elif target.target_type == "minimize":
                        merit += target.weight * abs(f)
                else:
                    merit += 1e6  # Penalty for invalid focal length
            
            elif target.name == "system_length":
                length = system.get_total_length()
                if target.target_type == "minimize":
                    merit += target.weight * length
                elif target.target_type == "target":
                    merit += target.weight * (length - target.target_value)**2
        
        return merit


class LensOptimizer:
    """Optimize optical system parameters"""
    
    def __init__(self, system: OpticalSystem, variables: List[OptimizationVariable],
                 targets: List[OptimizationTarget]):
        self.system = system
        self.variables = variables
        self.targets = targets
        self.merit_function = MeritFunction(system, targets)
    
    def optimize_simplex(self, max_iterations: int = 100, tolerance: float = 1e-6) -> OptimizationResult:
        """
        Nelder-Mead simplex optimization
        Simple but robust algorithm for lens optimization
        """
        n_vars = len(self.variables)
        
        # Initialize simplex (n+1 vertices in n-dimensional space)
        simplex = []
        current_values = [var.current_value for var in self.variables]
        
        # First vertex is current design
        simplex.append(current_values.copy())
        
        # Create n additional vertices by perturbing each variable
        for i in range(n_vars):
            vertex = current_values.copy()
            vertex[i] += self.variables[i].step_size
            vertex[i] = self.variables[i].clamp(vertex[i])
            simplex.append(vertex)
        
        # Evaluate merit for all vertices
        merit_values = [self._evaluate_design(vertex) for vertex in simplex]
        
        initial_merit = merit_values[0]
        variable_history = [dict(zip([v.name for v in self.variables], current_values))]
        merit_history = [initial_merit]
        
        # Simplex algorithm parameters
        alpha = 1.0  # Reflection
        gamma = 2.0  # Expansion
        rho = 0.5    # Contraction
        sigma = 0.5  # Shrinkage
        
        for iteration in range(max_iterations):
            # Sort vertices by merit (best to worst)
            order = sorted(range(len(merit_values)), key=lambda i: merit_values[i])
            simplex = [simplex[i] for i in order]
            merit_values = [merit_values[i] for i in order]
            
            # Check convergence
            merit_range = merit_values[-1] - merit_values[0]
            if merit_range < tolerance:
                break
            
            # Calculate centroid of best n points (excluding worst)
            centroid = [sum(simplex[i][j] for i in range(n_vars)) / n_vars 
                       for j in range(n_vars)]
            
            # Reflection
            worst = simplex[-1]
            reflected = [centroid[j] + alpha * (centroid[j] - worst[j]) 
                        for j in range(n_vars)]
            reflected = [self.variables[j].clamp(reflected[j]) for j in range(n_vars)]
            reflected_merit = self._evaluate_design(reflected)
            
            if merit_values[0] <= reflected_merit < merit_values[-2]:
                # Accept reflection
                simplex[-1] = reflected
                merit_values[-1] = reflected_merit
            elif reflected_merit < merit_values[0]:
                # Try expansion
                expanded = [centroid[j] + gamma * (reflected[j] - centroid[j])
                           for j in range(n_vars)]
                expanded = [self.variables[j].clamp(expanded[j]) for j in range(n_vars)]
                expanded_merit = self._evaluate_design(expanded)
                
                if expanded_merit < reflected_merit:
                    simplex[-1] = expanded
                    merit_values[-1] = expanded_merit
                else:
                    simplex[-1] = reflected
                    merit_values[-1] = reflected_merit
            else:
                # Contraction
                contracted = [centroid[j] + rho * (worst[j] - centroid[j])
                             for j in range(n_vars)]
                contracted = [self.variables[j].clamp(contracted[j]) for j in range(n_vars)]
                contracted_merit = self._evaluate_design(contracted)
                
                if contracted_merit < merit_values[-1]:
                    simplex[-1] = contracted
                    merit_values[-1] = contracted_merit
                else:
                    # Shrink simplex toward best point
                    best = simplex[0]
                    for i in range(1, len(simplex)):
                        simplex[i] = [best[j] + sigma * (simplex[i][j] - best[j])
                                     for j in range(n_vars)]
                        simplex[i] = [self.variables[j].clamp(simplex[i][j]) 
                                     for j in range(n_vars)]
                        merit_values[i] = self._evaluate_design(simplex[i])
            
            # Record history
            variable_history.append(dict(zip([v.name for v in self.variables], simplex[0])))
            merit_history.append(merit_values[0])
        
        # Best solution
        best_values = simplex[0]
        final_merit = merit_values[0]
        
        # Apply best values to system
        optimized_system = self._apply_variables(best_values)
        
        improvement = ((initial_merit - final_merit) / initial_merit * 100) if initial_merit > 0 else 0
        
        return OptimizationResult(
            success=True,
            iterations=iteration + 1,
            initial_merit=initial_merit,
            final_merit=final_merit,
            improvement=improvement,
            optimized_system=optimized_system,
            variable_history=variable_history,
            merit_history=merit_history,
            message=f"Converged after {iteration + 1} iterations"
        )
    
    def optimize_gradient_descent(self, max_iterations: int = 100, 
                                   learning_rate: float = 0.1,
                                   tolerance: float = 1e-6) -> OptimizationResult:
        """
        Gradient descent optimization with numerical gradients
        """
        current_values = [var.current_value for var in self.variables]
        initial_merit = self._evaluate_design(current_values)
        
        variable_history = [dict(zip([v.name for v in self.variables], current_values))]
        merit_history = [initial_merit]
        
        for iteration in range(max_iterations):
            # Calculate numerical gradient
            gradient = self._calculate_gradient(current_values)
            
            # Update variables
            new_values = []
            for i, (val, grad) in enumerate(zip(current_values, gradient)):
                new_val = val - learning_rate * grad
                new_val = self.variables[i].clamp(new_val)
                new_values.append(new_val)
            
            # Evaluate new design
            new_merit = self._evaluate_design(new_values)
            
            # Check convergence
            improvement = initial_merit - new_merit
            if abs(new_merit - merit_history[-1]) < tolerance:
                break
            
            # Accept new values
            current_values = new_values
            variable_history.append(dict(zip([v.name for v in self.variables], current_values)))
            merit_history.append(new_merit)
        
        optimized_system = self._apply_variables(current_values)
        final_merit = merit_history[-1]
        improvement = ((initial_merit - final_merit) / initial_merit * 100) if initial_merit > 0 else 0
        
        return OptimizationResult(
            success=True,
            iterations=iteration + 1,
            initial_merit=initial_merit,
            final_merit=final_merit,
            improvement=improvement,
            optimized_system=optimized_system,
            variable_history=variable_history,
            merit_history=merit_history,
            message=f"Completed {iteration + 1} iterations"
        )
    
    def _calculate_gradient(self, values: List[float]) -> List[float]:
        """Calculate numerical gradient using finite differences"""
        gradient = []
        epsilon = 1e-5
        
        f0 = self._evaluate_design(values)
        
        for i in range(len(values)):
            values_plus = values.copy()
            values_plus[i] += epsilon
            values_plus[i] = self.variables[i].clamp(values_plus[i])
            
            f_plus = self._evaluate_design(values_plus)
            grad = (f_plus - f0) / epsilon
            gradient.append(grad)
        
        return gradient
    
    def _evaluate_design(self, values: List[float]) -> float:
        """Evaluate merit function for given variable values"""
        system = self._apply_variables(values)
        return self.merit_function.evaluate(system)
    
    def _apply_variables(self, values: List[float]) -> OpticalSystem:
        """Create a system with variables applied"""
        # Deep copy the system
        system = copy.deepcopy(self.system)
        
        # Apply variable values
        for var, value in zip(self.variables, values):
            if var.parameter == "radius_of_curvature_1":
                system.elements[var.element_index].lens.radius_of_curvature_1 = value
            elif var.parameter == "radius_of_curvature_2":
                system.elements[var.element_index].lens.radius_of_curvature_2 = value
            elif var.parameter == "thickness":
                system.elements[var.element_index].lens.thickness = value
            elif var.parameter == "air_gap":
                if var.element_index < len(system.air_gaps):
                    system.air_gaps[var.element_index].thickness = value
        
        # Update positions after changes
        system._update_positions()
        
        return system


def create_doublet_optimizer(system: OpticalSystem, target_focal_length: float = 100.0) -> LensOptimizer:
    """
    Create optimizer for achromatic doublet
    Optimizes curvatures to minimize chromatic aberration while maintaining focal length
    """
    variables = [
        OptimizationVariable("R1 Crown", 0, "radius_of_curvature_1",
                           system.elements[0].lens.radius_of_curvature_1,
                           20.0, 500.0, 10.0),
        OptimizationVariable("R2 Crown", 0, "radius_of_curvature_2",
                           system.elements[0].lens.radius_of_curvature_2,
                           -500.0, -20.0, 10.0),
        OptimizationVariable("R1 Flint", 1, "radius_of_curvature_1",
                           system.elements[1].lens.radius_of_curvature_1,
                           -500.0, -20.0, 10.0),
        OptimizationVariable("R2 Flint", 1, "radius_of_curvature_2",
                           system.elements[1].lens.radius_of_curvature_2,
                           20.0, 500.0, 10.0),
    ]
    
    targets = [
        OptimizationTarget("chromatic_aberration", 0.0, weight=1.0, target_type="minimize"),
        OptimizationTarget("focal_length", target_focal_length, weight=100.0, target_type="target"),
    ]
    
    return LensOptimizer(system, variables, targets)
