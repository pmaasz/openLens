"""Tests for ISO 10110 drawing content (todo item 4)."""

import unittest

from src.io.export import ISO10110Generator
from src.lens import Lens
from src.optical_system import OpticalSystem


def _demo_system():
    system = OpticalSystem(name="Drawing Demo")
    front = Lens(
        name="Front",
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        thickness=5.0,
        diameter=40.0,
        material="BK7",
        bevel_1=0.3,
    )
    system.add_lens(front)
    system.add_lens(Lens(name="Rear", diameter=25.0), air_gap_before=5.0)
    return system


class TestIsoTitleBlock(unittest.TestCase):
    def test_title_block_fields(self):
        """Title block should carry drawing metadata."""
        svg = ISO10110Generator(_demo_system())._render_svg(1000, 700)
        self.assertIn("TITLE BLOCK", svg)
        self.assertIn("Drawing Demo", svg)
        self.assertIn("Dwg No", svg)
        self.assertIn("Units", svg)
        self.assertIn("Scale", svg)
        self.assertIn("EFL / BFL", svg)
        self.assertIn("Surfaces", svg)

    def test_empty_system_renders(self):
        """An empty system should still produce a valid drawing."""
        svg = ISO10110Generator(OpticalSystem(name="Empty"))._render_svg(800, 600)
        self.assertIn("TITLE BLOCK", svg)
        self.assertIn("ISO 10110 NOTES", svg)


class TestIsoDimensions(unittest.TestCase):
    def test_overall_dimensions(self):
        """Total track and max OD should be dimensioned."""
        svg = ISO10110Generator(_demo_system())._render_svg(1000, 700)
        self.assertIn("15.00 mm", svg)
        self.assertIn("Ø40.00", svg)


class TestIsoNotes(unittest.TestCase):
    def test_numbered_notes_present(self):
        """All eight ISO 10110 notes should be present."""
        svg = ISO10110Generator(_demo_system())._render_svg(1000, 700)
        for prefix in ("0/", "1/", "2/", "3/", "4/", "5/", "6/", "7/"):
            self.assertIn(prefix, svg)

    def test_centering_reflects_tilt(self):
        """4/ should quote the worst element tilt in arcminutes."""
        system = _demo_system()
        system.set_element_alignment(1, tilt_x=0.05)
        svg = ISO10110Generator(system)._render_svg(1000, 700)
        self.assertIn("≤ 3.0'", svg)

    def test_coating_note_lists_surfaces(self):
        """6/ should list per-surface coating labels."""
        from src.coating_designer import design_preset

        system = _demo_system()
        system.elements[0].lens.set_coating(
            1,
            [layer.to_dict() for layer in design_preset("MgF2 single-layer", 1.5168, 550.0)],
        )
        svg = ISO10110Generator(system)._render_svg(1000, 700)
        self.assertIn("MgF2 SLAR", svg)


class TestIsoTable(unittest.TestCase):
    def test_bevel_and_coat_columns(self):
        """Table should show bevel widths and coating labels."""
        svg = ISO10110Generator(_demo_system())._render_svg(1000, 700)
        self.assertIn("Bev", svg)
        self.assertIn("0.30", svg)

    def test_stop_marker(self):
        """A defined stop should be marked on the drawing."""
        system = _demo_system()
        system.set_aperture_stop(0, 20.0)
        svg = ISO10110Generator(system)._render_svg(1000, 700)
        self.assertIn("STOP", svg)
        self.assertIn("gap 0", svg)


if __name__ == "__main__":
    unittest.main()
