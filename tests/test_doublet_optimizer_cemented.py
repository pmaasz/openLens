"""Regression: the doublet optimiser must keep the cemented interface tied.

Two defects in ``create_doublet_optimizer``:

- "R2 Crown" was linked to the flint's front surface, so the cemented
  interface was driven by one variable - but a separate "R1 Flint" variable
  wrote the *same* parameter. They were applied in order and the later one
  won, so the interface came apart: ``_apply_variables([60, -45, -70, 200])``
  left the crown's R2 at -45 and the flint's R1 at -70. Two numbers for one
  surface.
- "R2 Flint" had positive bounds, ``[20, 500]``, while the doublet it is
  built from starts at about **-131 mm**. The optimiser therefore started
  outside its own box, with a bound penalty of ~2.3e10, and was pushed to
  flip the sign of the surface.
"""

import unittest

from openlens.optimizer import create_doublet_optimizer
from openlens.optical_system import create_doublet


class TestDoubletOptimizerCementedInterface(unittest.TestCase):
    """The two cemented surfaces must be one surface."""

    def setUp(self):
        self.doublet = create_doublet(focal_length=100, diameter=50)
        self.optimizer = create_doublet_optimizer(self.doublet, target_focal_length=100.0)
        self.names = [variable.name for variable in self.optimizer.variables]

    def test_no_variable_duplicates_the_cemented_interface(self):
        """A second variable writing the flint's R1 would break the tie."""
        self.assertNotIn(
            "R1 Flint",
            self.names,
            "a separate variable still writes the cemented interface",
        )

    def test_the_interface_is_driven_by_one_linked_variable(self):
        """R2 Crown carries the link to the flint's front surface."""
        crown_back = next(v for v in self.optimizer.variables if v.name == "R2 Crown")

        self.assertEqual(
            crown_back.linked_targets,
            [(1, "radius_of_curvature_1")],
            "the cemented interface is no longer linked",
        )

    def test_the_cemented_surfaces_stay_equal_after_applying_variables(self):
        """The issue's repro: crown R2 = -45 but flint R1 = -70."""
        self.optimizer._apply_variables([60.0, -45.0, -131.0])

        crown = self.optimizer.system.elements[0].lens
        flint = self.optimizer.system.elements[1].lens

        self.assertAlmostEqual(
            flint.radius_of_curvature_1,
            crown.radius_of_curvature_2,
            places=6,
            msg="the cemented surfaces came apart",
        )


class TestDoubletOptimizerStartsInsideItsBounds(unittest.TestCase):
    """The starting point has to be a legal point."""

    def setUp(self):
        self.doublet = create_doublet(focal_length=100, diameter=50)
        self.optimizer = create_doublet_optimizer(self.doublet, target_focal_length=100.0)

    def test_the_starting_point_has_no_bound_penalty(self):
        """The penalty was ~2.3e10, which dwarfs the real merit function."""
        values = [variable.current_value for variable in self.optimizer.variables]

        penalty = self.optimizer._bound_penalty(values)

        self.assertLess(
            penalty,
            1e-6,
            f"the optimiser starts outside its own bounds (penalty {penalty:.3e})",
        )

    def test_every_variable_starts_within_its_bounds(self):
        for variable in self.optimizer.variables:
            with self.subTest(variable=variable.name):
                self.assertTrue(
                    variable.is_valid(variable.current_value),
                    f"{variable.name} starts at {variable.current_value}, "
                    f"outside [{variable.min_value}, {variable.max_value}]",
                )

    def test_the_flint_back_surface_bounds_match_its_sign(self):
        """The flint's rear surface is concave, so its bounds are negative."""
        flint_back = next(v for v in self.optimizer.variables if v.name == "R2 Flint")

        self.assertLess(flint_back.max_value, 0.0)
        self.assertLess(flint_back.min_value, flint_back.max_value)

    def test_the_back_focal_length_survives_a_short_optimisation(self):
        """The real check: the optimiser must not wreck the lens."""
        try:
            self.optimizer.optimize(max_iterations=5)
        except Exception as e:  # pragma: no cover - reported below
            self.fail(f"the optimiser raised: {e}")

        doublet = self.optimizer.system
        crown = doublet.elements[0].lens
        flint = doublet.elements[1].lens

        self.assertAlmostEqual(
            flint.radius_of_curvature_1,
            crown.radius_of_curvature_2,
            places=6,
            msg="the cemented surfaces came apart during the optimisation",
        )
        self.assertGreater(crown.radius_of_curvature_1, 0.0)
        self.assertLess(crown.radius_of_curvature_2, 0.0)
        self.assertLess(flint.radius_of_curvature_2, 0.0)


if __name__ == "__main__":
    unittest.main()
