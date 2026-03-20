"""
Global Optimization Algorithms for Optical Systems.
Includes Simulated Annealing and Differential Evolution.
"""

import math
import random
import copy
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass

try:
    from .optimizer import OptimizationVariable, OptimizationResult, LensOptimizer, MeritFunction
    from .optical_system import OpticalSystem
except (ImportError, ValueError):
    import sys
    import os
    # Fix import path if running directly
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from src.optimizer import OptimizationVariable, OptimizationResult, LensOptimizer, MeritFunction
    from src.optical_system import OpticalSystem

class GlobalOptimizer(LensOptimizer):
    """
    Extends LensOptimizer with global search capabilities.
    """

    def optimize_simulated_annealing(self, 
                                     max_iterations: int = 1000, 
                                     initial_temperature: float = 100.0,
                                     cooling_rate: float = 0.95,
                                     restart_threshold: float = 1e-4,
                                     callback: Optional[Callable[[int, float, List[float]], None]] = None) -> OptimizationResult:
        """
        Simulated Annealing global optimization.
        """
        current_values = [var.current_value for var in self.variables]
        current_merit = self._evaluate_design(current_values)
        
        best_values = list(current_values)
        best_merit = current_merit
        
        temperature = initial_temperature
        
        variable_history = []
        merit_history = [current_merit]
        
        n_vars = len(self.variables)
        
        for iteration in range(max_iterations):
            # Callback
            if callback:
                callback(iteration, best_merit, best_values)

            # Create neighbor solution
            # Perturb one or more variables
            neighbor_values = list(current_values)
            
            # Adaptive perturbation based on temperature
            # At high T, larger jumps. At low T, smaller jumps.
            scale_factor = max(0.01, min(1.0, temperature / initial_temperature))
            
            # Select random variable to modify
            idx = random.randint(0, n_vars - 1)
            var = self.variables[idx]
            
            # Random perturbation
            # Range is heuristic: step_size * scale * Gaussian
            delta = var.step_size * scale_factor * random.gauss(0, 1)
            neighbor_values[idx] = var.clamp(neighbor_values[idx] + delta)
            
            # Evaluate neighbor
            neighbor_merit = self._evaluate_design(neighbor_values)
            
            # Acceptance probability
            delta_E = neighbor_merit - current_merit
            
            if delta_E < 0:
                # Better solution: always accept
                accept = True
            else:
                # Worse solution: accept with probability exp(-delta_E / T)
                # Avoid overflow
                if temperature < 1e-9:
                    prob = 0.0
                else:
                    prob = math.exp(-delta_E / temperature)
                
                accept = random.random() < prob
            
            if accept:
                current_values = neighbor_values
                current_merit = neighbor_merit
                
                # Update best found so far
                if current_merit < best_merit:
                    best_merit = current_merit
                    best_values = list(current_values)
            
            # Cool down
            temperature *= cooling_rate
            
            # History
            variable_history.append(dict(zip([v.name for v in self.variables], current_values)))
            merit_history.append(current_merit)
            
            # Early stop if converged (optional, usually SA runs full course)
            if temperature < 1e-6:
                break
                
        # Final refinement: Run local simplex from best point
        # Apply best values first
        self._apply_variables(best_values)
        # Update variable objects to reflect best values for local optimizer
        for i, val in enumerate(best_values):
            self.variables[i].current_value = val
            
        # Run local optimization
        local_result = self.optimize_simplex(max_iterations=50)
        
        # Combine results
        final_system = local_result.optimized_system
        final_merit = local_result.final_merit
        improvement = ((merit_history[0] - final_merit) / merit_history[0] * 100) if merit_history[0] > 0 else 0
        
        return OptimizationResult(
            success=True,
            iterations=iteration + 1 + local_result.iterations,
            initial_merit=merit_history[0],
            final_merit=final_merit,
            improvement=improvement,
            optimized_system=final_system,
            variable_history=variable_history + local_result.variable_history,
            merit_history=merit_history + local_result.merit_history,
            message=f"SA Converged after {iteration+1} iterations + {local_result.iterations} local steps"
        )

    def optimize_genetic(self,
                        population_size: int = 50,
                        generations: int = 50,
                        mutation_rate: float = 0.1,
                        crossover_rate: float = 0.7,
                        callback: Optional[Callable[[int, float, List[float]], None]] = None) -> OptimizationResult:
        """
        Genetic Algorithm global optimization.
        Uses real-valued encoding.
        """
        n_vars = len(self.variables)
        
        # Initialize population
        population = []
        for _ in range(population_size):
            individual = []
            for var in self.variables:
                # Random value in range
                val = random.uniform(var.min_value, var.max_value)
                individual.append(val)
            population.append(individual)
            
        # Add current design to population to ensure we don't regress
        current_design = [var.current_value for var in self.variables]
        population[0] = current_design
            
        best_overall_merit = float('inf')
        best_overall_design = None
        
        history_merit = []
        
        for gen in range(generations):
            # Callback
            if callback and best_overall_design:
                 callback(gen, best_overall_merit, best_overall_design)

            # Evaluate population
            merits = []
            for ind in population:
                m = self._evaluate_design(ind)
                merits.append(m)
                
            # Track best
            min_merit = min(merits)
            best_idx = merits.index(min_merit)
            
            if min_merit < best_overall_merit:
                best_overall_merit = min_merit
                best_overall_design = list(population[best_idx])
            
            history_merit.append(best_overall_merit)
            
            # Selection (Tournament)
            new_population = []
            
            # Elitism: Keep best
            new_population.append(list(best_overall_design))
            
            while len(new_population) < population_size:
                # Select two parents
                parent1 = self._tournament_select(population, merits)
                parent2 = self._tournament_select(population, merits)
                
                # Crossover
                if random.random() < crossover_rate:
                    child = self._crossover(parent1, parent2)
                else:
                    child = list(parent1)
                
                # Mutation
                self._mutate(child, mutation_rate)
                
                new_population.append(child)
                
            population = new_population
            
        # Final refinement
        self._apply_variables(best_overall_design)
        for i, val in enumerate(best_overall_design):
            self.variables[i].current_value = val
            
        local_result = self.optimize_simplex(max_iterations=50)
        
        return OptimizationResult(
            success=True,
            iterations=generations * population_size + local_result.iterations,
            initial_merit=history_merit[0],
            final_merit=local_result.final_merit,
            improvement=((history_merit[0] - local_result.final_merit)/history_merit[0]*100) if history_merit[0] > 0 else 0,
            optimized_system=local_result.optimized_system,
            variable_history=local_result.variable_history, # Only keep local history to save space
            merit_history=history_merit,
            message=f"GA Completed {generations} generations"
        )
        
    def _tournament_select(self, population, merits, k=3):
        selected_indices = random.sample(range(len(population)), k)
        best_idx = min(selected_indices, key=lambda i: merits[i])
        return population[best_idx]
        
    def _crossover(self, p1, p2):
        # Arithmetic crossover
        alpha = random.random()
        child = []
        for v1, v2 in zip(p1, p2):
            val = alpha * v1 + (1-alpha) * v2
            child.append(val)
        return child
        
    def _mutate(self, individual, rate):
        for i in range(len(individual)):
            if random.random() < rate:
                var = self.variables[i]
                # Gaussian mutation scaled by range
                sigma = (var.max_value - var.min_value) * 0.1
                individual[i] += random.gauss(0, sigma)
                individual[i] = var.clamp(individual[i])
