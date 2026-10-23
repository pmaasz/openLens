"""Regression: tracing a batch must prepare the element scene once.

#456: ``SystemRayTracer3D.trace_ray`` rebuilt its entire scene - walking the
node tree, recomputing every global transform and constructing a fresh
``LensRayTracer3D`` per element - inside the per-ray call. A 64x64 pupil
wavefront needs ~3200 traces, and the optimizer's MTF merit asks for one per
merit evaluation, so a single diffraction PSF on a doublet took ~1.7 s, almost
all of it rebuilding a scene that had not changed rather than refracting rays.

These tests pin the new contract:

- the element tracers and transforms are built once per tracer and reused;
- a change to the lens state they snapshotted (the wavefront sensor swaps the
  refractive index for every wavelength) is picked up without the caller
  knowing the cache exists;
- a change to the structure - positions - is picked up automatically, and
  ``invalidate()`` still forces a rebuild;
- and none of this changes a single traced path.
"""

import unittest
from unittest import mock

from openlens.ray import Ray3D
from openlens.vector3 import vec3
from openlens.lens import Lens
from openlens.optical_system import create_doublet
from openlens.tracer_3d import LensRayTracer3D, SystemRayTracer3D


def _paths(rays):
    """A comparable form of the traced paths: one tuple of points per ray."""
    return tuple(
        (
            ray.terminated,
            round(ray.optical_path_length, 9),
            tuple((round(p.x, 9), round(p.y, 9), round(p.z, 9)) for p in ray.path),
        )
        for ray in rays
    )


class _FlatElement:
    """A bare element for a duck-typed system without a node tree."""

    def __init__(self, lens, position):
        self.lens = lens
        self.position = position


def _flat_system(position=0.0):
    """A system without ``root``, so the tracer uses the flat-element path."""

    class _FlatSystem:
        def __init__(self):
            lens = Lens(
                name="Crown",
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=25.0,
                refractive_index=1.5,
            )
            self.elements = [_FlatElement(lens, position)]
            self.air_gaps = []

    return _FlatSystem()


class TestSceneIsPreparedOncePerBatch(unittest.TestCase):
    def setUp(self):
        self.system = create_doublet()
        self.tracer = SystemRayTracer3D(self.system)

    def _count_constructions(self):
        """Patch ``LensRayTracer3D.__init__`` and return the built lenses."""
        built = []
        original = LensRayTracer3D.__init__

        def counting_init(instance, lens, *args, **kwargs):
            built.append(lens)
            original(instance, lens, *args, **kwargs)

        patcher = mock.patch.object(LensRayTracer3D, "__init__", counting_init)
        patcher.start()
        self.addCleanup(patcher.stop)
        return built

    def test_each_element_tracer_is_built_once_for_a_whole_batch(self):
        built = self._count_constructions()

        rays = self.tracer.trace_off_axis_rays(0.0, num_rays=10)

        self.assertEqual(len(rays), 10)
        self.assertEqual(
            len(built),
            len(self.system.elements),
            "each ray rebuilt every element tracer "
            f"({len(built)} constructions for {len(self.system.elements)} elements)",
        )

    def test_the_scene_walk_does_not_scale_with_the_batch(self):
        from openlens.optical_node import OpticalNode

        def calls_for(num_rays):
            original = OpticalNode.get_global_transform
            calls = []

            def counting(instance):
                calls.append(instance)
                return original(instance)

            with mock.patch.object(OpticalNode, "get_global_transform", counting):
                SystemRayTracer3D(self.system).trace_off_axis_rays(0.0, num_rays=num_rays)
            return len(calls)

        one_ray = calls_for(1)
        ten_rays = calls_for(10)

        self.assertEqual(
            ten_rays,
            one_ray,
            "each ray re-walked the node tree and recomputed every transform",
        )
        # One call per element plus the recursion into its parent.
        self.assertLessEqual(one_ray, 2 * len(self.system.elements))

    def test_the_wavefront_grid_reuses_the_element_tracers(self):
        """The call site the optimizer's MTF merit actually uses (#456)."""
        from openlens.analysis.diffraction_psf import WavefrontSensor

        built = self._count_constructions()

        WavefrontSensor(self.system).get_pupil_wavefront(grid_size=8)

        self.assertEqual(
            len(built),
            len(self.system.elements),
            f"a 8x8 pupil grid built {len(built)} element tracers",
        )


class TestCachingChangesNothingOptical(unittest.TestCase):
    def setUp(self):
        self.system = create_doublet()
        self.lens = self.system.elements[0].lens

    def test_a_warm_cache_traces_the_same_paths_as_a_fresh_tracer(self):
        warm = SystemRayTracer3D(self.system)
        warm.trace_off_axis_rays(0.0, num_rays=3)  # prepare the batch

        for field in (0.0, 3.0):
            cached = warm.trace_off_axis_rays(field, num_rays=5)
            fresh = SystemRayTracer3D(self.system).trace_off_axis_rays(field, num_rays=5)
            self.assertEqual(_paths(cached), _paths(fresh))

    def test_a_refractive_index_change_is_picked_up_without_invalidate(self):
        """The wavefront sensor sets the index per wavelength and restores it.

        A cached tracer that snapshotted the old index would make every colour
        identical - the exact defect #314 fixed and test_wavefront_dispersion
        guards - so the index is part of what the batch validates.
        """
        tracer = SystemRayTracer3D(self.system)
        first = self._trace_single(tracer)

        self.lens.refractive_index = 1.7
        second = self._trace_single(tracer)

        fresh = self._trace_single(SystemRayTracer3D(self.system))
        self.assertNotEqual(first, second, "the cached tracer kept the old index")
        self.assertEqual(second, fresh)

    @staticmethod
    def _trace_single(tracer):
        return _paths(tracer.trace_off_axis_rays(0.0, num_rays=3))


class TestExplicitInvalidation(unittest.TestCase):
    def test_invalidate_rebuilds_after_a_position_change(self):
        """``invalidate()`` still forces a rebuild after a layout edit.

        The next trace would also notice the move through the scene signature;
        this pins the explicit path callers used before detection existed.
        """
        system = _flat_system(position=0.0)
        tracer = SystemRayTracer3D(system)
        before = _paths(tracer.trace_off_axis_rays(0.0, num_rays=3))

        system.elements[0].position = 12.0
        tracer.invalidate()
        after = _paths(tracer.trace_off_axis_rays(0.0, num_rays=3))

        fresh = _paths(SystemRayTracer3D(system).trace_off_axis_rays(0.0, num_rays=3))
        self.assertNotEqual(before, after)
        self.assertEqual(after, fresh)

    def test_invalidate_is_cheap_and_idempotent(self):
        tracer = SystemRayTracer3D(_flat_system())
        tracer.invalidate()
        tracer.invalidate()
        self.assertEqual(len(tracer.trace_off_axis_rays(0.0, num_rays=2)), 2)


class TestPositionChangesAreDetected(unittest.TestCase):
    """A long-lived tracer must not trace yesterday's layout (#614)."""

    def test_a_moved_node_is_picked_up_without_invalidate(self):
        system = create_doublet()
        tracer = SystemRayTracer3D(system)
        before = _paths(tracer.trace_off_axis_rays(0.0, num_rays=3))

        system.root.children[0].position = vec3(20.0, 0.0, 0.0)
        after = _paths(tracer.trace_off_axis_rays(0.0, num_rays=3))

        fresh = _paths(SystemRayTracer3D(system).trace_off_axis_rays(0.0, num_rays=3))
        self.assertNotEqual(before, after, "the cached scene kept the old position")
        self.assertEqual(after, fresh)

    def test_a_moved_flat_element_is_picked_up_without_invalidate(self):
        system = _flat_system(position=0.0)
        tracer = SystemRayTracer3D(system)
        before = _paths(tracer.trace_off_axis_rays(0.0, num_rays=3))

        system.elements[0].position = 12.0
        after = _paths(tracer.trace_off_axis_rays(0.0, num_rays=3))

        fresh = _paths(SystemRayTracer3D(system).trace_off_axis_rays(0.0, num_rays=3))
        self.assertNotEqual(before, after)
        self.assertEqual(after, fresh)

    def test_an_added_element_invalidates_the_scene(self):
        system = create_doublet()
        tracer = SystemRayTracer3D(system)
        tracer.trace_off_axis_rays(0.0, num_rays=2)

        # A second element at the same station still changes the traced path.
        system.add_lens(Lens(name="Extra", diameter=25.0), air_gap_before=1.0)
        after = _paths(tracer.trace_off_axis_rays(0.0, num_rays=2))
        fresh = _paths(SystemRayTracer3D(system).trace_off_axis_rays(0.0, num_rays=2))

        self.assertEqual(after, fresh)

    def test_a_moved_element_changes_a_spot_diagram(self):
        """The integration case: SpotDiagram keeps its tracer for its lifetime."""
        from openlens.analysis.spot_diagram import SpotDiagram

        system = create_doublet()
        diagram = SpotDiagram(system)
        plane = 120.0
        before = diagram.trace_spot(field_angle_y_deg=2.0, image_plane_x_mm=plane, num_rings=2)

        system.root.children[0].position = vec3(15.0, 0.0, 0.0)
        after = diagram.trace_spot(field_angle_y_deg=2.0, image_plane_x_mm=plane, num_rings=2)

        self.assertNotEqual(before["centroid"], after["centroid"])
        fresh = SpotDiagram(system).trace_spot(
            field_angle_y_deg=2.0, image_plane_x_mm=plane, num_rings=2
        )
        self.assertAlmostEqual(after["centroid"][0], fresh["centroid"][0], places=9)
        self.assertAlmostEqual(after["centroid"][1], fresh["centroid"][1], places=9)


class TestSingleLensTracerIsUnchanged(unittest.TestCase):
    """LensRayTracer3D itself keeps its documented per-instance behaviour."""

    def test_a_ray_still_refracts_at_both_surfaces(self):
        lens = Lens(
            name="Crown",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            thickness=5.0,
            diameter=25.0,
            refractive_index=1.5,
        )
        tracer = LensRayTracer3D(lens)
        ray = Ray3D(origin=vec3(-20.0, 2.0, 0.0), direction=vec3(1.0, 0.0, 0.0))

        tracer.trace_ray(ray, propagate_distance=0.0)

        self.assertFalse(ray.terminated)
        self.assertGreaterEqual(len(ray.path), 2)


if __name__ == "__main__":
    unittest.main()
