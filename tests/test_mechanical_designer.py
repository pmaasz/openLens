#!/usr/bin/env python3
"""
MechanicalDesigner: lens cells, spacers, BOM and assembly outputs.
"""

import unittest

from src.lens import Lens
from src.optical_system import OpticalSystem
from src.mechanical_designer import MechanicalDesigner


def _make_doublet():
    system = OpticalSystem(name="mech")
    system.add_lens(Lens(radius_of_curvature_1=50.0,
                         radius_of_curvature_2=-50.0,
                         thickness=4.0,
                         diameter=25.0,
                         refractive_index=1.5))
    system.add_lens(Lens(radius_of_curvature_1=-30.0,
                         radius_of_curvature_2=60.0,
                         thickness=3.0,
                         diameter=20.0,
                         refractive_index=1.6),
                    air_gap_before=5.0)
    return system


class TestMechanicalDesigner(unittest.TestCase):
    def setUp(self):
        self.designer = MechanicalDesigner(_make_doublet())

    def test_designs_one_cell_per_element(self):
        cells = self.designer.design_lens_cells(wall_thickness=2.0)
        self.assertEqual(len(cells), 2)

    def test_cell_clearance_and_outer_diameter(self):
        cell = self.designer.design_lens_cells()[0]
        # First lens has 25 mm diameter
        self.assertAlmostEqual(cell.inner_diameter, 25.0 + 0.1, places=9)
        self.assertAlmostEqual(cell.outer_diameter,
                               cell.inner_diameter + 2 * 2.0, places=9)

    def test_total_length_accounts_for_cells_and_spacers(self):
        self.designer.design_lens_cells()
        self.designer.calculate_spacers(target_spacing=[5.0])
        total = self.designer.calculate_total_length()
        expected_min = sum(c.length for c in self.designer.lens_cells)
        self.assertGreaterEqual(total, expected_min)

    def test_bom_lists_components(self):
        self.designer.design_lens_cells()
        bom = self.designer.generate_bom()
        self.assertIsInstance(bom, list)
        self.assertTrue(any('cell' in str(item).lower() for item in bom))

    def test_cad_parameters_exposed(self):
        self.designer.design_lens_cells()
        cad = self.designer.export_cad_parameters()
        self.assertIsInstance(cad, dict)


if __name__ == "__main__":
    unittest.main()
