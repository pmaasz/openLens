"""
Desensitization Optimization Module.
Optimizes optical systems for manufacturing yield by minimizing sensitivity to tolerances.
"""

import logging
import math
from typing import List, Dict, Optional, Callable

from .optimizer import (
    LensOptimizer,
    OptimizationResult,
    OptimizationTarget,
    MeritFunction,
)
from .optical_system import OpticalSystem
from .tolerancing import ToleranceOperand, ToleranceType, _apply_value

logger = logging.getLogger(__name__)


class RobustMeritFunction(MeritFunction):
    """
    Wraps a standard MeritFunction to add sensitivity penalties.
    Merit = Nominal_Merit + Weight * Sensitivity
    """

    #: Operand types the robust merit cannot perturb. FOCUS lives in the
    #: evaluation (it is a compensator, not a geometric quantity), and
    #: IRREGULARITY is a fringe count whose radius mapping is not exactly
    #: reversible - undoing the draw would leave the surface slightly
    #: different from the nominal one, and the run would drift.
    _UNPERTURBABLE = (ToleranceType.FOCUS, ToleranceType.IRREGULARITY)

    def __init__(
        self,
        system: OpticalSystem,
        targets: List[OptimizationTarget],
        tolerances: List[ToleranceOperand],
        sensitivity_weight: float = 1.0,
        constraints: Optional[Dict[str, float]] = None,
    ):
        super().__init__(system, targets, constraints)
        self.tolerances = tolerances
        self.sensitivity_weight = sensitivity_weight

    def evaluate(self, system: OpticalSystem) -> float:
        """Nominal merit plus the weighted sensitivity to the tolerances.

        Each toleranced parameter is perturbed by its maximum deviation, the
        merit is evaluated again, and the differences are combined in
        quadrature. The perturbation is applied with the same code the Monte
        Carlo analysis uses (:func:`openlens.tolerancing._apply_value`), so
        the two agree on what a tolerance does to a design - and every
        operand type the Monte Carlo can randomise can be measured here too.
        """
        nominal_merit = super().evaluate(system)

        sum_sq_diff = 0.0
        skipped = []

        for tol in self.tolerances:
            if tol.param_type in self._UNPERTURBABLE:
                skipped.append(f"Element {tol.element_index + 1} {tol.param_type.value}")
                continue

            delta = tol.max_val  # Check at the limit
            applied = _apply_value(
                system, tol.param_type, tol.element_index, delta, surface=tol.surface
            )
            if not applied:
                # The operand addresses nothing here (an air gap after the
                # last element, a decenter on the first one).
                skipped.append(f"Element {tol.element_index + 1} {tol.param_type.value}")
                continue
            try:
                merit_plus = super().evaluate(system)
            finally:
                # Undo the draw. Every operand the Monte Carlo randomises is
                # additive, so the inverse draw restores the nominal design
                # exactly.
                _apply_value(system, tol.param_type, tol.element_index, -delta, surface=tol.surface)

            # Difference
            diff = merit_plus - nominal_merit
            sum_sq_diff += diff * diff

        if skipped:
            logger.warning(
                "Robust merit: %d tolerance operand(s) could not be perturbed "
                "and are not in the sensitivity: %s",
                len(skipped),
                ", ".join(skipped),
            )

        sensitivity = math.sqrt(sum_sq_diff)

        return nominal_merit + self.sensitivity_weight * sensitivity


class DesensitizationOptimizer(LensOptimizer):
    """
    Optimizes for Yield.
    """

    def optimize_robust(
        self,
        tolerances: List[ToleranceOperand],
        sensitivity_weight: float = 1.0,
        max_iterations: int = 50,
        callback: Optional[Callable[[int, float, List[float]], None]] = None,
    ) -> OptimizationResult:
        """
        Run robust optimization.
        """
        # Replace default merit function with RobustMeritFunction
        original_merit_function = self.merit_function

        # Preserve constraints if they exist
        constraints = getattr(original_merit_function, "constraints", None)

        # The merit cache is keyed by the variable values alone, so the swap
        # has to drop it: otherwise every design the previous run saw is
        # scored with the previous run's merit function, and the new
        # sensitivity weight has no effect at all.
        self._set_merit_function(
            RobustMeritFunction(
                self.system,
                self.targets,
                tolerances,
                sensitivity_weight,
                constraints=constraints,
            )
        )

        try:
            # Run simplex
            return self.optimize_simplex(max_iterations=max_iterations, callback=callback)
        finally:
            # Restore the merit function - also when the run was cancelled
            # (the GUI's callback raises), otherwise the next ordinary
            # optimization on this instance silently uses the robust merit
            # with the old tolerance list.
            self._set_merit_function(original_merit_function)
