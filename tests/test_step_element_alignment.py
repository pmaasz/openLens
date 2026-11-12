#!/usr/bin/env python3
"""STEP export must place each element where the optical model puts it.

``StepExporter`` passed only ``elem.position`` to the solid builder, so every
exported solid sat on the global axis. An element deliberately decentered or
tilted - the layout the ray tracer and the assembly view use - exported
perfectly aligned, and the file still looked valid.

The exporter now applies each element's global transform (from the optical
tree, with the flat record as fallback) to every point of its solid, and
rotates the axis/direction entities with it.
"""

import math
import os
import re
import shutil
import tempfile
import unittest

from openlens.io.step_export import StepExporter
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem, create_doublet

_POINT_RE = re.compile(r"CARTESIAN_POINT\('([^']*)',\(([^)]*)\)\)")


def _point(text: str, name: str) -> tuple:
    for match in _POINT_RE.finditer(text):
        if match.group(1) == name:
            return tuple(float(value) for value in match.group(2).split(","))
    raise AssertionError(f"point {name!r} not found in the STEP file")


def _elements_of(text: str, name: str) -> list:
    return [
        tuple(float(value) for value in match.group(2).split(","))
        for match in _POINT_RE.finditer(text)
        if match.group(1) == name
    ]


def _direction(text: str, placement_name: str) -> tuple:
    placement = re.search(rf"AXIS2_PLACEMENT_3D\('{placement_name}',#\d+,(#\d+),#\d+\)", text)
    if placement is None:
        raise AssertionError(f"placement {placement_name!r} not found")
    axis = re.search(rf"{re.escape(placement.group(1))}=DIRECTION\('[^']*',\(([^)]*)\)\);", text)
    if axis is None:
        raise AssertionError(f"direction of {placement_name!r} not found")
    return tuple(float(value) for value in axis.group(1).split(","))


class _StepAlignmentFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def _export(self, system, name: str = "lens.step") -> str:
        path = os.path.join(self.directory, name)
        StepExporter(system).export(path)
        with open(path) as handle:
            return handle.read()

    def _single_element(self, **alignment) -> OpticalSystem:
        system = OpticalSystem("assembly")
        system.add_lens(Lens(name="Element", radius_of_curvature_1=100.0, diameter=20.0))
        if alignment:
            self.assertTrue(system.set_element_alignment(0, **alignment))
        return system


class TestElementPlacementIsExported(_StepAlignmentFixture):
    def test_a_decentered_element_moves_off_the_axis(self):
        text = self._export(self._single_element(decenter_y=5.0, decenter_z=2.0))

        # The element origin, and with it the vertex, sits at the node's
        # global position. STEP writes the optical axis along Z, with the
        # model's lateral Y/Z on X/Y.
        self.assertEqual(_point(text, "v1"), (5.0, 2.0, 0.0))

    def test_a_decentered_rim_moves_with_the_element(self):
        text = self._export(self._single_element(decenter_y=5.0))

        rim = _point(text, "e1")
        self.assertAlmostEqual(rim[0], 10.0 + 5.0, places=6)
        self.assertAlmostEqual(rim[1], 0.0, places=6)

    def test_a_tilted_element_rotates_its_axis(self):
        text = self._export(self._single_element(tilt_z=90.0))

        # A 90 deg tilt about the model's Z turns the optical axis from +X to
        # +Y, which is STEP's +X after the axis permutation.
        axis = _direction(text, "axis_cyl")
        self.assertAlmostEqual(axis[0], 1.0, places=6)
        self.assertAlmostEqual(axis[1], 0.0, places=6)
        self.assertAlmostEqual(axis[2], 0.0, places=6)

    def test_the_rim_stays_on_the_curved_surface_after_a_tilt(self):
        text = self._export(self._single_element(tilt_z=37.0, decenter_y=3.0, decenter_z=-1.0))

        centre = _point(text, "center1")
        rim = _point(text, "e1")
        self.assertAlmostEqual(math.dist(centre, rim), 100.0, places=6)

    def test_the_aligned_export_still_uses_the_global_axes(self):
        text = self._export(self._single_element())

        self.assertEqual(_direction(text, "axis_cyl"), (0.0, 0.0, 1.0))
        self.assertEqual(_point(text, "v1"), (0.0, 0.0, 0.0))


class TestAssemblyPlacement(_StepAlignmentFixture):
    def test_each_element_keeps_its_axial_position(self):
        system = create_doublet(focal_length=100.0, diameter=40.0)
        text = self._export(system)

        vertices = _elements_of(text, "v1")
        self.assertEqual(len(vertices), len(system.elements))
        for vertex, element in zip(vertices, system.elements):
            self.assertAlmostEqual(vertex[2], element.position, places=6)
            self.assertAlmostEqual(vertex[0], element.decenter_y, places=6)
            self.assertAlmostEqual(vertex[1], element.decenter_z, places=6)

    def test_two_differently_tilted_elements_get_two_axes(self):
        system = create_doublet(focal_length=100.0, diameter=40.0)
        self.assertTrue(system.set_element_alignment(1, tilt_z=30.0))
        text = self._export(system)

        placements = re.findall(r"AXIS2_PLACEMENT_3D\('axis_cyl',#\d+,#(\d+),#\d+\)", text)
        self.assertEqual(len(placements), 2)

        directions = []
        for axis_id in placements:
            match = re.search(rf"#{axis_id}=DIRECTION\('[^']*',\(([^)]*)\)\);", text)
            directions.append(tuple(float(value) for value in match.group(1).split(",")))
        self.assertNotEqual(directions[0], directions[1])
        self.assertEqual(directions[0], (0.0, 0.0, 1.0))


if __name__ == "__main__":
    unittest.main()
