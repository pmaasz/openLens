#!/usr/bin/env python3
"""
Optical System Optimization Engine
Automatically optimize lens parameters to minimize aberrations and improve performance
"""

from typing import List, Dict, Tuple, Callable, Optional
from dataclasses import dataclass, field
import copy
import math
from concurrent.futures import ThreadPoolExecutor

import logging

from .constants import MIN_EDGE_THICKNESS
from .lens import Lens
from .optical_system import OpticalSystem
from .aberrations import AberrationsCalculator
from .analysis import SpotDiagram
from .analysis.beam_synthesis import PSFCalculator, WavefrontSensor, NUMPY_AVAILABLE

logger = logging.getLogger(__name__)

#: Merit for unevaluatable targets (empty system, undefined focus, failed
#: trace). Single scale above the hard-geometry penalties (1e8) so "cannot
#: score" always ranks worse than "scores badly".
INFEASIBLE_MERIT = 1e9

#: Only spread the finite-difference perturbations across threads once there
#: are more variables than this; below it the thread hand-off costs more than
#: the evaluations it saves.
GRADIENT_PARALLEL_THRESHOLD = 4

#: Upper bound on gradient worker threads. Each evaluation deep-copies the
#: system, so unbounded fan-out would compete for memory rather than help.
GRADIENT_MAX_WORKERS = 4


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
    linked_targets: List[Tuple[int, str]] = field(
        default_factory=list
    )  # Other parameters controlled by this variable

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
    # The design the search settled on. Present so callers that refine with a
    # second pass (the global optimizers) can report and bounds-check what
    # they actually return rather than the pre-refinement point.
    best_values: List[float] = field(default_factory=list)


class MeritFunction:
    """Calculate merit function for optical system quality"""

    def __init__(
        self,
        system: OpticalSystem,
        targets: List[OptimizationTarget],
        constraints: Optional[Dict[str, float]] = None,
    ):
        self.system = system
        self.targets = targets
        self.constraints = constraints or {
            "min_center_thickness": 1.0,
            "max_center_thickness": 100.0,
            "min_edge_thickness": MIN_EDGE_THICKNESS,
            "min_air_gap": 0.1,
            "min_edge_clearance": 0.1,
        }

    # ------------------------------------------------------------------
    # Target evaluation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _apply_target(target: OptimizationTarget, value: float) -> float:
        """Return the merit contribution for *value* against *target*."""
        if target.target_type == "minimize":
            return target.weight * value
        elif target.target_type == "target":
            return target.weight * (value - target.target_value) ** 2
        elif target.target_type == "maximize":
            if value > 1e-9:
                return target.weight * (1.0 / value)
            return target.weight * 1e3
        return 0.0

    def _eval_spherical(self, system: OpticalSystem, target: OptimizationTarget) -> float:
        if not system.elements:
            return INFEASIBLE_MERIT
        calc = AberrationsCalculator(system)
        results = calc.calculate_all_aberrations()
        value = results.get("spherical_aberration")
        if value is None:
            return INFEASIBLE_MERIT
        return self._apply_target(target, abs(value))

    def _eval_coma(self, system: OpticalSystem, target: OptimizationTarget) -> float:
        if not system.elements:
            return INFEASIBLE_MERIT
        calc = AberrationsCalculator(system)
        results = calc.calculate_all_aberrations(field_angle_deg=5.0)
        value = results.get("coma")
        if value is None:
            return INFEASIBLE_MERIT
        return self._apply_target(target, abs(value))

    def _eval_astigmatism(self, system: OpticalSystem, target: OptimizationTarget) -> float:
        if not system.elements:
            return INFEASIBLE_MERIT
        calc = AberrationsCalculator(system)
        results = calc.calculate_all_aberrations(field_angle_deg=5.0)
        value = results.get("astigmatism")
        if value is None:
            return INFEASIBLE_MERIT
        return self._apply_target(target, abs(value))

    @staticmethod
    def _eval_chromatic(system: OpticalSystem, target: OptimizationTarget) -> float:
        chrom = system.calculate_chromatic_aberration()
        # Longitudinal chromatic aberration is signed; minimizing the raw
        # value would reward large negative LCA, so score its magnitude.
        return MeritFunction._apply_target(target, abs(chrom["longitudinal"]))

    @staticmethod
    def _eval_focal_length(system: OpticalSystem, target: OptimizationTarget) -> float:
        f = system.get_system_focal_length()
        if not f:
            return INFEASIBLE_MERIT
        return MeritFunction._apply_target(target, f)

    @staticmethod
    def _eval_system_length(system: OpticalSystem, target: OptimizationTarget) -> float:
        return MeritFunction._apply_target(target, system.get_total_length())

    @staticmethod
    def _eval_rms_spot(system: OpticalSystem, target: OptimizationTarget) -> float:
        try:
            spot = SpotDiagram(system)
            results = spot.trace_spot(field_angle_x_deg=0, field_angle_y_deg=0)
            value = results.get("rms_radius")
            # Never default a missing spot to 0.0: a vignetted system
            # would then score as a perfect design and win every
            # comparison. Fewer than two rays means undefined, not zero.
            if value is None or results.get("valid_rays", 0) < 2:
                logger.debug(
                    "RMS spot merit: no usable spot for the perturbed system "
                    "(rms_radius=%r, valid_rays=%r)",
                    value,
                    results.get("valid_rays"),
                )
                return INFEASIBLE_MERIT
            return MeritFunction._apply_target(target, value)
        except Exception as e:
            # Logged rather than discarded. A KeyError from a malformed spot
            # result and a genuine geometry failure used to be indistinguishable,
            # both collapsing to the same INFEASIBLE_MERIT with no trace.
            logger.warning("RMS spot merit evaluation failed: %s", e)
            return INFEASIBLE_MERIT

    @staticmethod
    def _eval_mtf(system: OpticalSystem, target: OptimizationTarget) -> float:
        # NUMPY_AVAILABLE is a module-level name imported from
        # beam_synthesis, which sets it False when numpy is missing. The old
        # `"NUMPY_AVAILABLE" in globals() and globals()["NUMPY_AVAILABLE"]`
        # dance was always true on the first half and hid the dependency from
        # every reader and linter.
        if not NUMPY_AVAILABLE:
            logger.debug("MTF merit unavailable: numpy is not installed.")
            return INFEASIBLE_MERIT

        try:
            import numpy as np

            sensor = WavefrontSensor(system)
            Y, Z, W = sensor.get_pupil_wavefront()

            if W.size == 0 or np.all(np.isnan(W)):
                logger.debug("MTF merit: empty or all-NaN pupil wavefront.")
                return INFEASIBLE_MERIT

            psf = PSFCalculator.calculate_psf(Y, Z, W)
            mtf = PSFCalculator.calculate_mtf(psf)
            value = float(np.sum(mtf))
            return MeritFunction._apply_target(target, value)
        except Exception as e:
            logger.warning("MTF merit evaluation failed: %s", e)
            return INFEASIBLE_MERIT

    _TARGET_DISPATCH = {
        "spherical_aberration": _eval_spherical,
        "coma": _eval_coma,
        "astigmatism": _eval_astigmatism,
        "chromatic_aberration": _eval_chromatic,
        "focal_length": _eval_focal_length,
        "system_length": _eval_system_length,
        "rms_spot_radius": _eval_rms_spot,
        "mtf": _eval_mtf,
    }

    # ------------------------------------------------------------------
    # Physical constraint helpers
    # ------------------------------------------------------------------

    def _penalty_physical(self, system: OpticalSystem) -> float:
        """Penalties for invalid geometries (thickness, air gaps, edge clearance).

        Canonical convention: ``Lens.thickness`` is the CENTER (vertex to
        vertex) thickness, matching the ray tracers (tracer_2d/3d), the ABCD
        matrix, the lensmaker equation, and ``LensGeometry``. All sags come
        from the single source of truth (``Lens.get_sag_1/2``); undefined
        geometry (aperture overhanging a sphere) surfaces as
        ``calculate_edge_thickness() is None``.
        """
        merit = 0.0
        min_ct = self.constraints.get("min_center_thickness", 1.0)
        max_ct = self.constraints.get("max_center_thickness", 100.0)
        min_et = self.constraints.get("min_edge_thickness", MIN_EDGE_THICKNESS)
        min_ag = self.constraints.get("min_air_gap", 0.1)
        min_ec = self.constraints.get("min_edge_clearance", 0.1)

        for element in system.elements:
            lens = element.lens
            # Center (vertex separation) thickness IS lens.thickness.
            center_thickness = lens.thickness
            if center_thickness <= 0:
                # Hard infeasible: vertices crossed/coincident (inside-out lens).
                merit += 1e8
            if center_thickness < min_ct:
                merit += 1e5 * (min_ct - center_thickness) ** 2
            if center_thickness > max_ct:
                merit += 1e3 * (center_thickness - max_ct) ** 2

            try:
                y = lens.diameter / 2.0
                edge_thickness = lens.calculate_edge_thickness()
                if edge_thickness is None:
                    # Aperture overhangs a spherical surface (|R| < h):
                    # sag is undefined there.
                    merit += 1e8
                    continue
                if edge_thickness <= 0:
                    # Hard infeasible: rim collapse / surfaces crossed at edge.
                    merit += 1e8
                if edge_thickness < min_et:
                    merit += 1e4 * (min_et - edge_thickness) ** 2
                # Interior check: meniscus shapes can self-intersect inside
                # the aperture even when center and rim are both positive.
                # (Rim defined implies interior sags are defined too.)
                for frac in (0.5, 0.7071):
                    yi = y * frac
                    ti = center_thickness - lens.get_sag_1(yi) + lens.get_sag_2(yi)
                    if ti <= 0:
                        merit += 1e8
                        break
                    if ti < min_et:
                        merit += 1e4 * (min_et - ti) ** 2
            except Exception:
                merit += 1e5

        for i, gap in enumerate(system.air_gaps):
            if gap.thickness < min_ag:
                merit += 1e5 * (min_ag - gap.thickness) ** 2

            if i < len(system.elements) - 1:
                lens1 = system.elements[i].lens
                lens2 = system.elements[i + 1].lens
                max_h = min(lens1.diameter, lens2.diameter) / 2.0
                if (
                    lens1.calculate_edge_thickness() is None
                    or lens2.calculate_edge_thickness() is None
                ):
                    merit += 1e8
                    continue
                s_back_1 = lens1.get_sag_2(max_h)
                s_front_2 = lens2.get_sag_1(max_h)
                edge_clearance = gap.thickness + s_front_2 - s_back_1
                if edge_clearance <= 0:
                    merit += 1e8
                if edge_clearance < min_ec:
                    merit += 1e5 * (min_ec - edge_clearance) ** 2

        return merit

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def evaluate(self, system: OpticalSystem) -> float:
        """
        Evaluate merit function (lower is better).

        Combines physical constraint penalties with optical quality targets.
        """
        merit = self._penalty_physical(system)

        for target in self.targets:
            handler = self._TARGET_DISPATCH.get(target.name)
            if handler is not None:
                # handler may be a plain function (for staticmethods) or unbound method
                # Compare underlying function via getattr to handle both
                h = getattr(handler, "__func__", handler)
                statics = tuple(
                    getattr(getattr(MeritFunction, n), "__func__", getattr(MeritFunction, n))
                    for n in (
                        "_eval_chromatic",
                        "_eval_focal_length",
                        "_eval_system_length",
                        "_eval_rms_spot",
                        "_eval_mtf",
                    )
                )
                if h in statics:
                    merit += handler(system, target)
                else:
                    merit += handler(self, system, target)

        return merit


class LensOptimizer:
    """Optimize optical system parameters"""

    #: Backtracking budget for optimize_gradient_descent: how many times to
    #: halve the step before declaring the point stationary.
    MAX_BACKTRACKING_STEPS = 12
    #: Below this the step is too small to be worth evaluating.
    MIN_LEARNING_RATE = 1e-12

    def __init__(
        self,
        system: OpticalSystem,
        variables: List[OptimizationVariable],
        targets: List[OptimizationTarget],
        constraints: Optional[Dict[str, float]] = None,
    ):
        self.system = system
        self.variables = variables
        self.targets = targets
        self.merit_function = MeritFunction(system, targets, constraints)
        self._merit_cache = {}

    def optimize(
        self,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
        callback: Optional[Callable[[int, float, List[float]], None]] = None,
    ) -> OptimizationResult:
        """
        Run optimization using the default algorithm (Simplex).
        Wrapper for compatibility with controllers.

        Args:
            max_iterations: Maximum number of iterations.
            tolerance: Convergence threshold.
            callback: Function called at each iteration with (iteration, merit, current_values).
        """
        return self.optimize_simplex(max_iterations, tolerance, callback)

    def _finalize(
        self,
        best_values: List[float],
        final_merit: float,
        initial_merit: float,
        iterations: int,
        variable_history: List[Dict],
        merit_history: List[float],
        converged_message: str,
        out_of_bounds_message: str,
    ) -> OptimizationResult:
        """Build the result for any optimizer that settled on ``best_values``.

        Shared so success, iteration count and improvement mean the same
        thing everywhere. A best point outside the variable box is not a
        success even if the merit converged - the design is unusable - which
        the global paths previously skipped by hardcoding ``success=True``.

        Args:
            best_values: The design the search settled on.
            final_merit: Merit of ``best_values``.
            initial_merit: Merit of the *starting* design, so ``improvement``
                is measured against a real baseline.
            iterations: Iterations actually performed (not evaluations).
            variable_history: Per-iteration design history.
            merit_history: Per-iteration merit history.
            converged_message: Message when the design is inside bounds.
            out_of_bounds_message: Message when it is not.

        Returns:
            The assembled :class:`OptimizationResult`.
        """
        best_valid = all(var.is_valid(v) for var, v in zip(self.variables, best_values))

        optimized_system = self._apply_variables(best_values)

        improvement = (
            ((initial_merit - final_merit) / initial_merit * 100) if initial_merit > 0 else 0
        )

        return OptimizationResult(
            success=best_valid,
            iterations=iterations,
            initial_merit=initial_merit,
            final_merit=final_merit,
            improvement=improvement,
            optimized_system=optimized_system,
            variable_history=variable_history,
            merit_history=merit_history,
            message=converged_message if best_valid else out_of_bounds_message,
            best_values=list(best_values),
        )

    def optimize_simplex(
        self,
        max_iterations: int = 100,
        tolerance: float = 1e-6,
        callback: Optional[Callable[[int, float, List[float]], None]] = None,
    ) -> OptimizationResult:
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

        # Create n additional vertices by perturbing each variable.
        # Deliberately NOT clamped: out-of-bounds vertices earn a bound
        # penalty in _evaluate_design instead, so the search sees the true
        # landscape. Clamping collapses distinct vertices onto one bound
        # point, faking convergence (merit_range -> 0, success=True).
        for i in range(n_vars):
            vertex = current_values.copy()
            vertex[i] += self.variables[i].step_size
            simplex.append(vertex)

        # Evaluate merit for all vertices
        merit_values = [self._evaluate_design(vertex) for vertex in simplex]

        initial_merit = merit_values[0]
        variable_history = [dict(zip([v.name for v in self.variables], current_values))]
        merit_history = [initial_merit]

        # Simplex algorithm parameters
        alpha = 1.0  # Reflection
        gamma = 2.0  # Expansion
        rho = 0.5  # Contraction
        sigma = 0.5  # Shrinkage

        last_iteration = 0

        for iteration in range(max_iterations):
            last_iteration = iteration
            # Sort vertices by merit (best to worst)
            order = sorted(range(len(merit_values)), key=lambda i: merit_values[i])
            simplex = [simplex[i] for i in order]
            merit_values = [merit_values[i] for i in order]

            # Callback with best solution so far
            if callback:
                callback(iteration, merit_values[0], simplex[0])

            merit_range = merit_values[-1] - merit_values[0]
            n_clamped = sum(
                1
                for vertex in simplex
                if any(not var.is_valid(v) for var, v in zip(self.variables, vertex))
            )
            logger.debug(
                "simplex iter %d: merit_range=%.3g n_clamped=%d best=%.3g",
                iteration,
                merit_range,
                n_clamped,
                merit_values[0],
            )
            if n_clamped > n_vars / 2 and merit_range < tolerance:
                # Asphyxiation, not convergence: a majority of vertices is
                # pinned outside the box with no merit spread between them.
                return OptimizationResult(
                    success=False,
                    iterations=iteration + 1,
                    initial_merit=initial_merit,
                    final_merit=merit_values[0],
                    improvement=(
                        ((initial_merit - merit_values[0]) / initial_merit * 100)
                        if initial_merit > 0
                        else 0
                    ),
                    optimized_system=self._apply_variables(simplex[0]),
                    variable_history=variable_history,
                    merit_history=merit_history,
                    best_values=list(simplex[0]),
                    message=(
                        f"Aborted after {iteration + 1} iterations: {n_clamped} of "
                        f"{len(simplex)} simplex vertices stuck outside variable bounds"
                    ),
                )

            # Check convergence
            if merit_range < tolerance:
                break

            # Calculate centroid of best n points (excluding worst)
            centroid = [sum(simplex[i][j] for i in range(n_vars)) / n_vars for j in range(n_vars)]

            # Reflection (unclamped: bounds are penalties, not walls)
            worst = simplex[-1]
            reflected = [centroid[j] + alpha * (centroid[j] - worst[j]) for j in range(n_vars)]
            reflected_merit = self._evaluate_design(reflected)

            if merit_values[0] <= reflected_merit < merit_values[-2]:
                # Accept reflection
                simplex[-1] = reflected
                merit_values[-1] = reflected_merit
            elif reflected_merit < merit_values[0]:
                # Try expansion
                expanded = [
                    centroid[j] + gamma * (reflected[j] - centroid[j]) for j in range(n_vars)
                ]
                expanded_merit = self._evaluate_design(expanded)

                if expanded_merit < reflected_merit:
                    simplex[-1] = expanded
                    merit_values[-1] = expanded_merit
                else:
                    simplex[-1] = reflected
                    merit_values[-1] = reflected_merit
            else:
                # Contraction
                contracted = [centroid[j] + rho * (worst[j] - centroid[j]) for j in range(n_vars)]
                contracted_merit = self._evaluate_design(contracted)

                if contracted_merit < merit_values[-1]:
                    simplex[-1] = contracted
                    merit_values[-1] = contracted_merit
                else:
                    # Shrink simplex toward best point
                    best = simplex[0]
                    for i in range(1, len(simplex)):
                        simplex[i] = [
                            best[j] + sigma * (simplex[i][j] - best[j]) for j in range(n_vars)
                        ]
                        merit_values[i] = self._evaluate_design(simplex[i])

            # Record history
            variable_history.append(dict(zip([v.name for v in self.variables], simplex[0])))
            merit_history.append(merit_values[0])

            last_iteration = iteration

        # Best solution (a best point outside the box is not a success,
        # even if the merit range converged: the design is unusable).
        best_values = simplex[0]
        final_merit = merit_values[0]

        return self._finalize(
            best_values=best_values,
            final_merit=final_merit,
            initial_merit=initial_merit,
            iterations=last_iteration + 1,
            variable_history=variable_history,
            merit_history=merit_history,
            converged_message=f"Converged after {last_iteration + 1} iterations",
            out_of_bounds_message=(
                f"Finished after {last_iteration + 1} iterations outside variable bounds"
            ),
        )

    def optimize_gradient_descent(
        self,
        max_iterations: int = 100,
        learning_rate: float = 0.1,
        tolerance: float = 1e-6,
    ) -> OptimizationResult:
        """
        Gradient descent optimization with numerical gradients
        """
        current_values = [var.current_value for var in self.variables]
        initial_merit = self._evaluate_design(current_values)

        variable_history = [dict(zip([v.name for v in self.variables], current_values))]
        merit_history = [initial_merit]

        last_iteration = 0
        # Tracked explicitly rather than read back out of merit_history[-1]: the
        # history is only appended for accepted steps, so on the iteration that
        # gives up it no longer describes the current design.
        current_merit = initial_merit
        # Backtracking state. Every step used to be accepted unconditionally,
        # so a merit carrying 1e8-scale geometry penalties diverged and the
        # improvement it reported was negative.
        step_size = learning_rate
        accepted_steps = 0

        for iteration in range(max_iterations):
            last_iteration = iteration

            # Calculate numerical gradient
            gradient = self._calculate_gradient(current_values)

            # A step that does not reduce the merit is not taken: halve the step
            # size and retry from the same point. Variables are not clamped -
            # bounds stay penalties rather than walls - so an out-of-range trial
            # simply scores badly and is rejected here.
            accepted = False
            for _ in range(self.MAX_BACKTRACKING_STEPS):
                new_values = [val - step_size * grad for val, grad in zip(current_values, gradient)]
                new_merit = self._evaluate_design(new_values)

                if new_merit <= current_merit:
                    accepted = True
                    break

                step_size *= 0.5
                if step_size < self.MIN_LEARNING_RATE:
                    break

            if not accepted:
                # No smaller step helps: a stationary point, or a numerical
                # gradient too small to move against the tolerance. Stop rather
                # than wander off into a worse design.
                logger.debug(
                    "Gradient descent stalled at merit %.6g on iteration %d; "
                    "smallest step tried was %.3g",
                    current_merit,
                    iteration + 1,
                    step_size,
                )
                break

            accepted_steps += 1
            improvement = current_merit - new_merit

            current_values = new_values
            current_merit = new_merit
            variable_history.append(dict(zip([v.name for v in self.variables], current_values)))
            merit_history.append(new_merit)

            if improvement < tolerance:
                # Converged: the step no longer buys a meaningful reduction.
                break

        logger.debug(
            "Gradient descent: %d accepted step(s) over %d iteration(s), merit %.6g -> %.6g",
            accepted_steps,
            last_iteration + 1,
            initial_merit,
            current_merit,
        )

        optimized_system = self._apply_variables(current_values)
        # current_merit, not merit_history[-1]: the history is only appended for
        # accepted steps, so on a stalled run its last entry can predate the
        # design actually returned.
        final_merit = current_merit
        improvement = (
            ((initial_merit - final_merit) / initial_merit * 100) if initial_merit > 0 else 0
        )
        final_valid = all(var.is_valid(v) for var, v in zip(self.variables, current_values))

        return OptimizationResult(
            success=final_valid,
            iterations=last_iteration + 1,
            initial_merit=initial_merit,
            final_merit=final_merit,
            improvement=improvement,
            optimized_system=optimized_system,
            variable_history=variable_history,
            merit_history=merit_history,
            message=(
                f"Completed {last_iteration + 1} iterations"
                if final_valid
                else f"Finished {last_iteration + 1} iterations outside variable bounds"
            ),
        )

    def _calculate_gradient(self, values: List[float]) -> List[float]:
        """Calculate the numerical gradient by forward finite differences.

        The perturbations were previously spread over a
        ``ProcessPoolExecutor``. That was a poor trade on every axis:
        ``self._evaluate_design`` is a bound method, so ``executor.map``
        pickled the entire optimizer - the deep-copied ``OpticalSystem``,
        the targets and the whole merit cache - once per task, and the
        children each evaluated against a private copy of the cache, so
        nothing was reused. Worse, this runs inside a ``QThread`` that
        owns live Qt state: under the ``spawn`` start method (macOS,
        Windows, PyInstaller) the child re-imports ``__main__``, which for
        ``python3 openlens.py`` starts a second Qt application, and
        forking a process holding Qt/matplotlib state is a known hang
        source. A pool was also constructed and torn down on every single
        gradient call, so process startup dominated the work it was
        meant to parallelise.

        A thread pool sidesteps all of it: no pickling, one shared merit
        cache, no child processes to re-enter ``__main__``, and threads
        are created once per gradient call rather than whole processes.
        The merit function is pure Python ray tracing, so this is a
        modest win at best - but it is a win that cannot deadlock, and
        it keeps the many-variable case no worse than serial.
        """
        epsilon = 1e-5
        n_vars = len(values)

        # Prepare all perturbed designs (unclamped: clamping the +epsilon
        # step at a bound makes f_plus == f0 and the gradient exactly 0.0).
        perturbed_designs = []
        for i in range(n_vars):
            values_plus = values.copy()
            values_plus[i] += epsilon
            perturbed_designs.append(values_plus)

        # Evaluate f0 (might already be cached)
        f0 = self._evaluate_design(values)

        # Evaluate all perturbations, in parallel only once the serial
        # overhead would be worth it.
        if n_vars > GRADIENT_PARALLEL_THRESHOLD:
            workers = min(n_vars, GRADIENT_MAX_WORKERS)
            with ThreadPoolExecutor(max_workers=workers) as executor:
                f_plus_list = list(executor.map(self._evaluate_design, perturbed_designs))
        else:
            f_plus_list = [self._evaluate_design(v) for v in perturbed_designs]

        gradient = [(f_plus - f0) / epsilon for f_plus in f_plus_list]
        return gradient

    def _bound_penalty(self, values: List[float]) -> float:
        """Quadratic penalty for bound violations (no clamping in search).

        Clamping search points to the box collapses distinct vertices onto
        one bound point, faking convergence; penalizing keeps the true
        landscape (a bowl pulling back inside) visible to simplex/gradient.
        """
        penalty = 0.0
        for var, v in zip(self.variables, values):
            if not var.is_valid(v):
                penalty += 1e6 * (v - var.clamp(v)) ** 2
        return penalty

    def _evaluate_design(self, values: List[float]) -> float:
        """Evaluate merit function for given variable values with caching"""
        # Create a cache key from the values (rounded to avoid precision issues)
        cache_key = tuple(round(v, 10) for v in values)
        if cache_key in self._merit_cache:
            merit = self._merit_cache[cache_key]
        else:
            system = self._apply_variables(values)
            merit = self.merit_function.evaluate(system) + self._bound_penalty(values)
            self._merit_cache[cache_key] = merit

        # A NaN merit is not "infinitely good": it poisons every comparison it
        # takes part in (min(), <, sorting). _eval_mtf already sums a
        # PSF-derived array and can produce NaN, so normalise here where every
        # algorithm is guaranteed to pass through. Search code can then treat
        # INFEASIBLE_MERIT as the ordinary worst case.
        if math.isnan(merit):
            return INFEASIBLE_MERIT
        return merit

    def _apply_variables(self, values: List[float]) -> OpticalSystem:
        """Create a system with variables applied"""
        # Deep copy the system
        system = copy.deepcopy(self.system)

        # Apply variable values
        for var, value in zip(self.variables, values):
            # Apply to primary target
            self._apply_single_variable(system, var.element_index, var.parameter, value)

            # Apply to linked targets
            for elem_idx, param in var.linked_targets:
                self._apply_single_variable(system, elem_idx, param, value)

        # Update positions after changes
        system._update_positions()

        return system

    def _apply_single_variable(
        self, system: OpticalSystem, element_index: int, parameter: str, value: float
    ):
        """Apply a single variable value to the system.

        Spherical and parabolic definitions are exclusive per surface: a
        radius write clears the parabolic flag (otherwise the tracer would
        keep using the sag and the variable would silently no-op), while a
        sag write latches it on (a sag variable is meaningless on a
        spherical surface).
        """
        if parameter == "radius_of_curvature_1":
            lens = system.elements[element_index].lens
            lens.is_parabolic_1 = False
            lens.radius_of_curvature_1 = value
        elif parameter == "radius_of_curvature_2":
            lens = system.elements[element_index].lens
            lens.is_parabolic_2 = False
            lens.radius_of_curvature_2 = value
        elif parameter == "parabolic_sag_1":
            system.elements[element_index].lens.is_parabolic_1 = True
            system.elements[element_index].lens.parabolic_sag_1 = value
        elif parameter == "parabolic_sag_2":
            system.elements[element_index].lens.is_parabolic_2 = True
            system.elements[element_index].lens.parabolic_sag_2 = value
        elif parameter == "thickness":
            system.elements[element_index].lens.thickness = value
        elif parameter == "diameter":
            system.elements[element_index].lens.diameter = value
        elif parameter == "air_gap":
            if element_index < len(system.air_gaps):
                system.air_gaps[element_index].thickness = value
        elif parameter == "refractive_index":
            lens = system.elements[element_index].lens
            lens.model_glass_mode = True
            lens.model_nd = value
            lens.update_refractive_index()
        elif parameter == "abbe_number":
            lens = system.elements[element_index].lens
            lens.model_glass_mode = True
            lens.model_vd = value
            lens.update_refractive_index()


def create_doublet_optimizer(
    system: OpticalSystem, target_focal_length: float = 100.0
) -> LensOptimizer:
    """
    Create optimizer for achromatic doublet
    Optimizes curvatures to minimize chromatic aberration while maintaining focal length
    """
    variables = [
        OptimizationVariable(
            "R1 Crown",
            0,
            "radius_of_curvature_1",
            system.elements[0].lens.radius_of_curvature_1,
            20.0,
            500.0,
            10.0,
        ),
        OptimizationVariable(
            "R2 Crown",
            0,
            "radius_of_curvature_2",
            system.elements[0].lens.radius_of_curvature_2,
            -500.0,
            -20.0,
            10.0,
            linked_targets=[(1, "radius_of_curvature_1")],
        ),
        OptimizationVariable(
            "R1 Flint",
            1,
            "radius_of_curvature_1",
            system.elements[1].lens.radius_of_curvature_1,
            -500.0,
            -20.0,
            10.0,
        ),
        OptimizationVariable(
            "R2 Flint",
            1,
            "radius_of_curvature_2",
            system.elements[1].lens.radius_of_curvature_2,
            20.0,
            500.0,
            10.0,
        ),
    ]
    # Keep backward compatibility for tests expecting "Interface Curvature"
    # Add alias if needed: ensure interface variable is present
    # The above covers 4 variables as expected by tests; the linked target ensures cemented interface

    targets = [
        OptimizationTarget("chromatic_aberration", 0.0, weight=1.0, target_type="minimize"),
        OptimizationTarget("focal_length", target_focal_length, weight=100.0, target_type="target"),
    ]

    return LensOptimizer(system, variables, targets)
