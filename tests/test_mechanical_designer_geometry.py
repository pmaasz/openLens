#!/usr/bin/env python3
"""The mechanical stack must follow the optical geometry.

``MechanicalDesigner`` sized every cell as 10 mm - it looked for a
``center_thickness`` attribute ``Lens`` does not have - and every spacer as
10 mm, because it looked for an ``element_spacing`` attribute
``OpticalSystem`` does not have. The housing therefore had no relation to the
element thicknesses or the air gaps it was meant to hold.
"""

import unittest

from openlens.lens import Lens
from openlens.mechanical_designer import MechanicalDesigner
from openlens.optical_system import OpticalSystem


def _system():
    system = OpticalSystem("mechanical")
    system.add_lens(Lens(thickness=30.0, diameter=25.0, refractive_index=1.5168))
    system.add_lens(
        Lens(thickness=5.0, diameter=20.0, refractive_index=1.5168),
        air_gap_before=20.0,
    )
    return system


class TestMechanicalGeometry(unittest.TestCase):
    def setUp(self):
        self.system = _system()
        self.designer = MechanicalDesigner(self.system)

    def test_cell_length_follows_the_element_thickness(self):
        cells = self.designer.design_lens_cells()

        self.assertAlmostEqual(cells[0].length, 30.0 + MechanicalDesigner.CELL_MARGIN_MM)
        self.assertAlmostEqual(cells[1].length, 5.0 + MechanicalDesigner.CELL_MARGIN_MM)

    def test_spacers_follow_the_air_gaps(self):
        spacers = self.designer.calculate_spacers()

        self.assertEqual([spacer.thickness for spacer in spacers], [20.0])

    def test_an_explicit_target_spacing_still_wins(self):
        spacers = self.designer.calculate_spacers(target_spacing=[7.5])

        self.assertEqual([spacer.thickness for spacer in spacers], [7.5])

    def test_a_duck_typed_spacing_list_is_still_used(self):
        class _DuckSystem:
            elements = [object(), object()]
            element_spacing = [4.0]

        spacers = MechanicalDesigner(_DuckSystem()).calculate_spacers()

        self.assertEqual([spacer.thickness for spacer in spacers], [4.0])

    def test_the_total_reconciles_with_the_optical_stack(self):
        self.designer.design_lens_cells()
        self.designer.calculate_spacers()

        margin = len(self.system.elements) * MechanicalDesigner.CELL_MARGIN_MM
        self.assertAlmostEqual(
            self.designer.calculate_total_length(),
            self.system.get_total_length() + margin,
        )

    def test_the_reported_reproduction(self):
        """The numbers from the issue, end to end."""
        self.designer.design_lens_cells()
        self.designer.calculate_spacers()

        self.assertEqual(
            [round(cell.length, 6) for cell in self.designer.lens_cells],
            [30.0 + MechanicalDesigner.CELL_MARGIN_MM, 5.0 + MechanicalDesigner.CELL_MARGIN_MM],
        )
        # The optical stack is 30 + 20 + 5 = 55 mm.
        self.assertAlmostEqual(self.system.get_total_length(), 55.0)


if __name__ == "__main__":
    unittest.main()
