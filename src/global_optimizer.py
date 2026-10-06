"""
Global Optimization Algorithms for Optical Systems.
Includes Simulated Annealing and Differential Evolution.
"""

import logging
import math
import random
from typing import List, Dict, Optional, Callable

from .optimizer import (
    OptimizationVariable,
    OptimizationResult,
    LensOptimizer,
    OptimizationTarget,
)
from .optical_system import OpticalSystem

logger = logging.getLogger(__name__)


class GlobalOptimizer(LensOptimizer):
    """
    Extends LensOptimizer with global search capabilities.
    """

    def __init__(
        self,
        system: OpticalSystem,
        variables: List[OptimizationVariable],
        targets: List[OptimizationTarget],
        constraints: Optional[Dict[str, float]] = None,
        seed: Optional[int] = None,
    ):
        super().__init__(system, variables, targets, constraints)
        if seed is not None:
            random.seed(seed)

    def optimize_simulated_annealing(
        self,
        max_iterations: int = 1000,
        initial_temperature: float = 100.0,
        cooling_rate: float = 0.95,
        restart_threshold: float = 1e-4,
        callback: Optional[Callable[[int, float, List[float]], None]] = None,
    ) -> OptimizationResult:
        """
        Simulated Annealing global optimization.
        """
        current_values = [var.current_value for var in self.variables]
        current_merit = self._evaluate_design(current_values)
        # Captured now because the annealing loop reassigns current_merit to
        # whichever neighbour it is currently sitting on.
        starting_merit = current_merit

        best_values = list(current_values)
        best_merit = current_merit

        temperature = initial_temperature

        variable_history = []
        merit_history = [current_merit]

        n_vars = len(self.variables)

        # temperature / initial_temperature is evaluated every iteration, so a
        # non-positive initial_temperature raised ZeroDivisionError on the very
        # first pass. Clamped rather than rejected: a zero *cooling* start is a
        # reasonable thing for a caller to mean.
        if initial_temperature <= 0:
            logger.warning(
                "initial_temperature=%r is not positive; clamping to a small "
                "positive value so annealing stays well defined.",
                initial_temperature,
            )
            initial_temperature = 1e-6

        # max_iterations <= 0 leaves the loop body unentered, and `iteration` was
        # then read below for the iteration count - UnboundLocalError. -1 makes
        # that read yield 0 iterations.
        iteration = -1

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

        # Final refinement: Run local simplex from the best point found.
        # The start is passed explicitly. It used to be transferred by writing
        # into self.variables[i].current_value - i.e. by mutating the caller's
        # OptimizationVariable objects, which the GUI also reads and saves, so
        # a simulated-annealing run silently overwrote the user's inputs. The
        # adjacent self._apply_variables(best_values) was dead code: it returns
        # a deepcopy and never mutates self.system.
        local_result = self.optimize_simplex(max_iterations=50, start=best_values)

        # Combine results. initial_merit is the *starting* design's merit:
        # merit_history[0] is the best of the first step, after a random
        # perturbation, so it understates the starting point and inflates
        # improvement. success comes from _finalize, which validates the bounds
        # instead of asserting True.
        return self._finalize(
            best_values=local_result.best_values,
            final_merit=local_result.final_merit,
            initial_merit=starting_merit,
            iterations=iteration + 1 + local_result.iterations,
            variable_history=variable_history + local_result.variable_history,
            merit_history=merit_history + local_result.merit_history,
            converged_message=(
                f"SA Converged after {iteration + 1} iterations"
                f" + {local_result.iterations} local steps"
            ),
            out_of_bounds_message=(
                f"SA finished after {iteration + 1} iterations"
                f" + {local_result.iterations} local steps outside variable bounds"
            ),
        )

    def optimize_genetic(
        self,
        population_size: int = 50,
        generations: int = 50,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7,
        callback: Optional[Callable[[int, float, List[float]], None]] = None,
    ) -> OptimizationResult:
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

        best_overall_merit = float("inf")
        # Seeded with the starting design so it is never None. It used to
        # start as None and only be replaced when some design beat inf, so a
        # merit that never beat inf (NaN, or generations=0) left it None and
        # the elitism copy below raised TypeError.
        best_overall_design = list(current_design)
        best_overall_merit = self._evaluate_design(best_overall_design)
        # Captured separately: best_overall_merit is replaced whenever a
        # better design is found, so by the end it holds the best merit seen,
        # not the merit of the starting design.
        starting_merit = best_overall_merit

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

            # isfinite guards the comparison: NaN < x is False for every x, so
            # a NaN-scored generation would otherwise be skipped silently and
            # the elite kept unchanged.
            if math.isfinite(min_merit) and min_merit < best_overall_merit:
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

        # Final refinement. As in the simulated-annealing path: the start is
        # passed explicitly rather than written into the caller's variable
        # objects, and the _apply_variables call was dead code.
        local_result = self.optimize_simplex(max_iterations=50, start=best_overall_design)

        # starting_merit is the merit of the design the search began from.
        # history_merit[0] would be the best of generation 0 - after up to 50
        # random mutations - and is empty entirely when generations=0, so
        # neither can serve as the baseline. iterations counts generations,
        # not the generations*population_size evaluations the old code
        # reported, and success comes from _finalize's bounds check rather
        # than a hardcoded True.
        return self._finalize(
            best_values=local_result.best_values,
            final_merit=local_result.final_merit,
            initial_merit=starting_merit,
            iterations=generations + local_result.iterations,
            variable_history=local_result.variable_history,
            merit_history=history_merit,
            converged_message=f"GA Completed {generations} generations",
            out_of_bounds_message=(
                f"GA finished {generations} generations outside variable bounds"
            ),
        )

    def _tournament_select(self, population, merits, k=3):
        """Return the best of k random contestants.

        k is clamped to the population size: random.sample raises
        "Sample larger than population" for population_size < k, which the GUI
        was one config change away from.
        """
        if not population:
            raise ValueError("cannot select from an empty population")
        k = max(1, min(k, len(population)))
        selected_indices = random.sample(range(len(population)), k)
        best_idx = min(selected_indices, key=lambda i: merits[i])
        return population[best_idx]

    def _crossover(self, p1, p2):
        # Arithmetic crossover
        alpha = random.random()
        child = []
        for v1, v2 in zip(p1, p2):
            val = alpha * v1 + (1 - alpha) * v2
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
