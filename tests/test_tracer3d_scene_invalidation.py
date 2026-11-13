#!/usr/bin/env python3
"""A cached tracer must notice a layout edit.

``SystemRayTracer3D`` prepares each element's tracer once and reuses it for
the whole batch. The batch validated the lens state only, so after an element
was moved - through the model API, or by assigning the node transform the way
the assembly editor does - the cached tracer silently traced the old geometry.
``invalidate()`` existed, but no production caller used it.
"""

import unittest
from unittest import mock

from openlens.lens import Lens
from openlens.optical_node import OpticalAssembly, OpticalElement
from openlens.optical_system import OpticalSystem
from openlens.ray import Ray3D
from openlens.tracer_3d import LensRayTracer3D, SystemRayTracer3D
from openlens.vector3 import vec3


def _singlet_lens():
    return Lens(
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        refractive_index=1.5168,
        thickness=5.0,
        diameter=25.0,
    )


def _system():
    system = OpticalSystem("singlet")
    system.add_lens(_singlet_lens())
    return system


def _last_point(tracer):
    """Trace one ray through *tracer* and return where it ends up."""
    ray = Ray3D(vec3(-10.0, 5.0, 0.0), vec3(1.0, 0.0, 0.0))
    tracer.trace_ray(ray)
    return (round(ray.path[-1].x, 6), round(ray.path[-1].y, 6), round(ray.path[-1].z, 6))


class _FlatElement:
    """A bare element for a duck-typed system without a node tree."""

    def __init__(self, lens, position):
        self.lens = lens
        self.position = position


class _FlatSystem:
    def __init__(self):
        self.elements = [_FlatElement(_singlet_lens(), 0.0)]
        self.air_gaps = []


class TestSceneEditIsPickedUp(unittest.TestCase):
    def test_a_moved_node_is_picked_up_without_invalidate(self):
        """The report's repro: assign the node position between two traces."""
        system = _system()
        tracer = SystemRayTracer3D(system)
        before = _last_point(tracer)

        system.root.children[0].position = vec3(20.0, 0.0, 0.0)
        after = _last_point(tracer)

        fresh = _last_point(SystemRayTracer3D(system))
        self.assertNotEqual(before, after, "the cached tracer kept the old position")
        self.assertEqual(after, fresh)

    def test_a_tilted_node_is_picked_up_without_invalidate(self):
        system = _system()
        tracer = SystemRayTracer3D(system)
        before = _last_point(tracer)

        system.root.children[0].rotation = vec3(0.0, 3.0, 0.0)
        after = _last_point(tracer)

        fresh = _last_point(SystemRayTracer3D(system))
        self.assertNotEqual(before, after, "the cached tracer kept the old tilt")
        self.assertEqual(after, fresh)

    def test_an_alignment_edit_is_picked_up_without_invalidate(self):
        """The GUI mutates the node in place; the model must announce it."""
        system = _system()
        tracer = SystemRayTracer3D(system)
        before = _last_point(tracer)

        system.set_element_alignment(0, decenter_y=4.0)
        after = _last_point(tracer)

        fresh = _last_point(SystemRayTracer3D(system))
        self.assertNotEqual(before, after, "the cached tracer kept the old alignment")
        self.assertEqual(after, fresh)

    def test_a_moved_assembly_is_picked_up_without_invalidate(self):
        """Moving a container moves the elements inside it."""
        assembly = OpticalAssembly(name="Group")
        assembly.add_child(OpticalElement(element_model=_singlet_lens(), name="Inner"))
        system = OpticalSystem("nested")
        system.add_assembly(assembly, position=10.0)

        tracer = SystemRayTracer3D(system)
        before = _last_point(tracer)

        assembly.position = vec3(40.0, 0.0, 0.0)
        after = _last_point(tracer)

        self.assertNotEqual(before, after, "the cached tracer kept the assembly where it was")
        self.assertEqual(after, _last_point(SystemRayTracer3D(system)))

    def test_an_added_element_is_picked_up_without_invalidate(self):
        system = _system()
        tracer = SystemRayTracer3D(system)
        before = _last_point(tracer)

        system.add_lens(_singlet_lens(), air_gap_before=10.0)
        after = _last_point(tracer)

        self.assertNotEqual(before, after, "the cached tracer kept the one-element scene")
        self.assertEqual(after, _last_point(SystemRayTracer3D(system)))

    def test_a_flat_system_position_change_is_picked_up(self):
        """A duck-typed system has no node tree to announce the edit."""
        system = _FlatSystem()
        tracer = SystemRayTracer3D(system)
        before = _last_point(tracer)

        system.elements[0].position = 12.0
        after = _last_point(tracer)

        self.assertNotEqual(before, after)
        self.assertEqual(after, _last_point(SystemRayTracer3D(system)))

    def test_an_unchanged_scene_is_still_prepared_once(self):
        """The edit check must not cost a scene rebuild per ray."""
        system = _system()
        tracer = SystemRayTracer3D(system)
        built = []
        original = LensRayTracer3D.__init__

        def counting_init(instance, lens, *args, **kwargs):
            built.append(lens)
            original(instance, lens, *args, **kwargs)

        with mock.patch.object(LensRayTracer3D, "__init__", counting_init):
            tracer.trace_ray(Ray3D(vec3(-10.0, 5.0, 0.0), vec3(1.0, 0.0, 0.0)))
            tracer.trace_ray(Ray3D(vec3(-10.0, 0.0, 0.0), vec3(1.0, 0.0, 0.0)))

        self.assertEqual(len(built), len(system.elements))


if __name__ == "__main__":
    unittest.main()
