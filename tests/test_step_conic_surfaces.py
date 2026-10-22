#!/usr/bin/env python3
"""STEP export must not write a conic surface as a mismatched sphere.

``StepExporter`` computed the rim point from the lens model's true sag but
always emitted a ``SPHERICAL_SURFACE`` of the stored vertex radius. For a
parabola with a 1.25 mm rim sag the sphere's sag at that rim is 0.50 mm: the
rim does not lie on the exported surface and the solid does not close.

A sphere through both the vertex and the rim still cannot carry the parabolic
profile, so the exporter now refuses the lens with a diagnostic instead of
writing a plausible-looking wrong solid. Spherical and flat surfaces keep
exporting, including a parabolic surface whose stored sag is zero (a plane).
"""

import os
import re
import shutil
import tempfile
import unittest

from openlens.io.step_export import StepExporter
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


class _StepExportFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.directory)

    def _path(self, name: str = "lens.step") -> str:
        return os.path.join(self.directory, name)

    def _system(self, *lenses: Lens) -> OpticalSystem:
        system = OpticalSystem("test")
        for lens in lenses:
            system.add_lens(lens)
        return system

    def _export(self, target, name: str = "lens.step"):
        path = self._path(name)
        summary = StepExporter(target).export(path)
        return summary, path


class TestNonSphericalSurfacesAreRefused(_StepExportFixture):
    def test_a_parabolic_front_surface_is_refused(self):
        system = self._system(
            Lens(name="Parabola", is_parabolic_1=True, parabolic_sag_1=1.25, diameter=20.0)
        )

        with self.assertRaises(ValueError) as caught:
            self._export(system)

        message = str(caught.exception)
        self.assertIn("parabolic", message.lower())
        self.assertIn("Parabola", message)
        self.assertIn("front", message)
        # The diagnosis has to make the mismatch checkable: the model's rim
        # sag and the sag of the sphere the writer used to emit.
        self.assertIn("1.250000", message)
        self.assertIn("0.501256", message)
        self.assertFalse(os.path.exists(self._path()), "a refused export wrote a partial file")

    def test_a_conic_front_surface_is_refused(self):
        system = self._system(
            Lens(
                name="Conic",
                radius_of_curvature_1=50.0,
                conic_constant_1=-2.0,
                diameter=20.0,
            )
        )

        with self.assertRaises(ValueError) as caught:
            self._export(system)

        self.assertIn("conic", str(caught.exception).lower())
        self.assertIn("Conic", str(caught.exception))
        self.assertFalse(os.path.exists(self._path()))

    def test_a_parabolic_back_surface_is_refused(self):
        system = self._system(
            Lens(name="BackParabola", is_parabolic_2=True, parabolic_sag_2=-0.8, diameter=20.0)
        )

        with self.assertRaises(ValueError) as caught:
            self._export(system)

        self.assertIn("back", str(caught.exception))
        self.assertFalse(os.path.exists(self._path()))

    def test_one_conic_element_refuses_the_whole_assembly(self):
        system = self._system(
            Lens(name="Sphere", diameter=20.0),
            Lens(name="Parabola", is_parabolic_1=True, parabolic_sag_1=1.25, diameter=20.0),
        )

        with self.assertRaises(ValueError) as caught:
            self._export(system)

        # The error names the element that cannot be written, not the first.
        self.assertIn("'Parabola'", str(caught.exception))
        self.assertFalse(os.path.exists(self._path()), "a refused export wrote a partial file")


class TestRepresentableSurfacesStillExport(_StepExportFixture):
    def test_a_spherical_lens_exports_a_solid(self):
        summary, path = self._export(self._system(Lens(diameter=20.0)))

        self.assertEqual(summary["shapes"], 1)
        with open(path) as handle:
            text = handle.read()
        self.assertIn("SPHERICAL_SURFACE", text)
        self.assertIn("MANIFOLD_SOLID_BREP", text)

    def test_the_rim_of_the_exported_sphere_lies_on_it(self):
        lens = Lens(radius_of_curvature_1=100.0, diameter=20.0)
        _, path = self._export(self._system(lens))

        with open(path) as handle:
            text = handle.read()
        match = re.search(r"SPHERICAL_SURFACE\('sphere1',#\d+,([0-9.]+)\)", text)
        self.assertIsNotNone(match, "the exported solid has no front sphere")
        radius = float(match.group(1))

        height = lens.diameter / 2.0
        sag = lens.get_sag_1(height)
        # The vertex is at z=0 and the centre at z=radius, so the rim point
        # (height, 0, sag) must be exactly one radius from the centre.
        distance_squared = height * height + (radius - sag) ** 2
        self.assertAlmostEqual(distance_squared, radius * radius, places=6)

    def test_a_zero_sag_parabolic_surface_exports_as_a_plane(self):
        system = self._system(Lens(is_parabolic_1=True, parabolic_sag_1=0.0, diameter=20.0))

        summary, path = self._export(system)

        self.assertEqual(summary["shapes"], 1)
        with open(path) as handle:
            text = handle.read()
        self.assertIn("PLANE", text)

    def test_a_conic_constant_on_a_flat_surface_is_still_flat(self):
        system = self._system(
            Lens(radius_of_curvature_1=float("inf"), conic_constant_1=-2.0, diameter=20.0)
        )

        summary, _ = self._export(system)

        self.assertEqual(summary["shapes"], 1)


if __name__ == "__main__":
    unittest.main()
