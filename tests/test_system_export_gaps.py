#!/usr/bin/env python3
"""
System export must not read an attribute that does not exist.

LensElement has no air_gap_before field - gaps live on the system as
system.air_gaps, rebuilt by _rebuild_from_tree:

    vars(element) == ['decenter_y', 'decenter_z', 'lens', 'lens_id',
                      'position', 'thickness', 'tilt_x', 'tilt_y', 'tilt_z']

Both the OpticStudio and SVG system exporters read elem.air_gap_before, so
every system export raised:

    AttributeError: 'LensElement' object has no attribute 'air_gap_before'

That includes the 1-element case, since the attribute is read on the first
element too.

_gap_before derives it from the system instead: air_gaps[i] is the gap *after*
element i, so the gap before element i is air_gaps[i - 1].
"""

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

from src.export_formats import OpticStudioExporter, SVGExporter, _gap_before
from src.lens import Lens
from src.optical_system import OpticalSystem


def _lens(name, r1=50.0, r2=-50.0, thickness=5.0, index=1.5):
    return Lens(
        name=name,
        radius_of_curvature_1=r1,
        radius_of_curvature_2=r2,
        thickness=thickness,
        diameter=25.0,
        refractive_index=index,
    )


def _system(count=1, gap=2.0):
    system = OpticalSystem(name="Sys")
    system.add_lens(_lens("A"))
    for i in range(1, count):
        system.add_lens(
            _lens(
                "L%d" % i,
                r1=-40.0,
                r2=40.0,
                thickness=3.0,
                index=1.6,
            ),
            air_gap_before=gap,
        )
    return system


class TestGapBefore(unittest.TestCase):
    def test_first_element_has_no_gap(self):
        self.assertEqual(_gap_before(_system(2), 0), 0.0)

    def test_second_element_sees_the_first_gap(self):
        self.assertAlmostEqual(_gap_before(_system(2), 1), 2.0)

    def test_third_element_sees_the_second_gap(self):
        self.assertAlmostEqual(_gap_before(_system(3), 2), 2.0)

    def test_single_element_system(self):
        """The issue's repro: the attribute was read on element 0 too."""
        self.assertEqual(_gap_before(_system(1), 0), 0.0)

    def test_index_past_the_end_does_not_raise(self):
        system = _system(2)
        self.assertEqual(_gap_before(system, 5), 0.0)

    def test_negative_index_does_not_raise(self):
        self.assertEqual(_gap_before(_system(2), -1), 0.0)

    def test_gap_matches_element_spacing(self):
        """Cross-check against the positions the system itself computed."""
        system = _system(2)
        first, second = system.elements
        self.assertAlmostEqual(
            _gap_before(system, 1), second.position - (first.position + first.thickness)
        )


class TestOpticStudioSystemExport(unittest.TestCase):
    def _export(self, system):
        handle, path = tempfile.mkstemp(suffix=".txt")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        OpticStudioExporter.export_system(system, path)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def _surface_rows(self, text):
        return [line for line in text.splitlines() if line[:4].strip().isdigit()]

    def test_single_element_export_succeeds(self):
        """Regression: AttributeError before the fix."""
        text = self._export(_system(1))
        self.assertIn("SYSTEM PRESCRIPTION DATA", text)

    def test_three_element_export_succeeds(self):
        text = self._export(_system(3))
        self.assertIn("Number of Elements: 3", text)

    def test_no_element_also_exports(self):
        self.assertIn("Number of Elements: 0", self._export(OpticalSystem(name="E")))

    def test_single_element_writes_two_surfaces(self):
        rows = self._surface_rows(self._export(_system(1)))
        self.assertEqual(len(rows), 2)

    def test_gap_becomes_an_infinity_surface_row(self):
        rows = self._surface_rows(self._export(_system(2)))
        gap_rows = [r for r in rows if "Infinity" in r]
        self.assertEqual(len(gap_rows), 1)
        # Columns: number, type, radius, thickness, glass. The gap row is an
        # Infinity-radius STANDARD surface whose thickness is the gap.
        self.assertAlmostEqual(float(gap_rows[0].split()[3]), 2.0)

    def test_gap_row_precedes_the_lens_it_belongs_to(self):
        rows = self._surface_rows(self._export(_system(2)))
        gap_index = next(i for i, r in enumerate(rows) if "Infinity" in r)
        # The gap must sit immediately before the second lens's front surface.
        self.assertAlmostEqual(float(rows[gap_index + 1].split()[2]), -40.0)

    def test_two_gaps_produce_two_gap_rows(self):
        rows = self._surface_rows(self._export(_system(3)))
        self.assertEqual(len([r for r in rows if "Infinity" in r]), 2)

    def test_row_count_is_two_surfaces_plus_one_gap_each(self):
        for count in (1, 2, 3):
            with self.subTest(elements=count):
                rows = self._surface_rows(self._export(_system(count)))
                self.assertEqual(len(rows), 2 * count + (count - 1))

    def test_zero_gap_emits_no_extra_row(self):
        system = OpticalSystem(name="T")
        system.add_lens(_lens("A"))
        system.add_lens(_lens("B", r1=-40.0, r2=40.0, thickness=3.0))
        rows = self._surface_rows(self._export(system))
        self.assertEqual(len(rows), 4)
        self.assertFalse([r for r in rows if "Infinity" in r])


class TestSVGSystemExport(unittest.TestCase):
    def _export(self, system):
        handle, path = tempfile.mkstemp(suffix=".svg")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        SVGExporter.export_system(system, path)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_single_element_export_succeeds(self):
        """Regression: AttributeError before the fix."""
        self.assertIn("<svg", self._export(_system(1)))

    def test_output_is_valid_xml(self):
        ET.fromstring(self._export(_system(3)))

    def test_one_rect_per_element(self):
        svg = self._export(_system(3))
        self.assertEqual(svg.count('class="lens-stroke"'), 3)

    def test_gap_shifts_later_lenses_apart(self):
        """The x offset must grow by the gap, or elements overlap."""
        tight = OpticalSystem(name="T")
        tight.add_lens(_lens("A"))
        tight.add_lens(_lens("B", r1=-40.0, r2=40.0, thickness=3.0))
        spaced = OpticalSystem(name="T")
        spaced.add_lens(_lens("A"))
        spaced.add_lens(_lens("B", r1=-40.0, r2=40.0, thickness=3.0), air_gap_before=10.0)

        def second_rect_x(svg):
            marker = 'class="lens-stroke"'
            first = svg.index(marker)
            second = svg.index(marker, first + 1)
            line = svg[svg.rindex("<rect", 0, second) : second]
            return float(line.split('x="')[1].split('"')[0])

        self.assertGreater(second_rect_x(self._export(spaced)), second_rect_x(self._export(tight)))

    def test_empty_system_exports(self):
        self.assertIn("<svg", self._export(OpticalSystem(name="E")))


if __name__ == "__main__":
    unittest.main()
