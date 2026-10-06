#!/usr/bin/env python3
"""
SVG output must escape interpolated names and materials.

Lens and system names come from untrusted JSON (validate_lens_name accepts
any string up to 100 chars) and were interpolated straight into SVG text
nodes with no escaping anywhere in src/.

A name of '</text><script>alert(1)</script>' produced a file that was both
script-bearing when opened in a browser and structurally invalid XML - and a
plain '&' in a name was enough to break the XML on its own.

Every interpolated value is now passed through xml.sax.saxutils.escape.
"""

import os
import tempfile
import unittest
import xml.etree.ElementTree as ET

from src.export_formats import SVGExporter
from src.io.export import ISO10110Generator
from src.lens import Lens
from src.optical_system import OpticalSystem

SVG_NS = "{http://www.w3.org/2000/svg}"

SCRIPT_NAME = "</text><script>alert(1)</script>"
AMP_NAME = "R&D \"quoted\" <tag> & 'apostrophe'"
UNICODE_NAME = "Ø 25mm ünïcode SiO₂"


def _lens(name=SCRIPT_NAME, material="N-BK7"):
    return Lens(
        name=name,
        material=material,
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=5.0,
        diameter=25.0,
        refractive_index=1.5,
    )


def _system(name=SCRIPT_NAME, material="N-BK7"):
    system = OpticalSystem(name=name)
    system.add_lens(_lens(name, material))
    return system


class _SVGBase(unittest.TestCase):
    def _export(self, fn):
        handle, path = tempfile.mkstemp(suffix=".svg")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        fn(path)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def export_lens_svg(self, lens):
        return self._export(lambda p: SVGExporter.export_lens(lens, p))

    def export_iso_svg(self, system):
        return self._export(lambda p: ISO10110Generator(system).generate_svg(p))


class TestNoScriptInjection(_SVGBase):
    def test_script_in_lens_name_is_neutralised(self):
        """Regression: raw <script> appeared in the SVG."""
        svg = self.export_lens_svg(_lens())
        self.assertNotIn("<script>", svg)
        self.assertNotIn("</script>", svg)

    def test_script_in_system_name_is_neutralised(self):
        svg = self.export_iso_svg(_system())
        self.assertNotIn("<script>", svg)

    def test_script_in_material_is_neutralised(self):
        svg = self.export_lens_svg(_lens(name="Fine", material=SCRIPT_NAME))
        self.assertNotIn("<script>", svg)

    def test_escaped_entities_are_present_instead(self):
        svg = self.export_lens_svg(_lens())
        self.assertIn("&lt;script&gt;", svg)


class TestOutputIsWellFormedXML(_SVGBase):
    """A plain '&' was enough to make the file invalid XML."""

    def test_ampersand_name_parses(self):
        svg = self.export_lens_svg(_lens(name=AMP_NAME))
        ET.fromstring(svg)

    def test_ampersand_material_parses(self):
        svg = self.export_lens_svg(_lens(name="Fine", material=AMP_NAME))
        ET.fromstring(svg)

    def test_iso_title_block_parses(self):
        ET.fromstring(self.export_iso_svg(_system(name=AMP_NAME, material=AMP_NAME)))

    def test_unicode_name_parses(self):
        ET.fromstring(self.export_lens_svg(_lens(name=UNICODE_NAME)))

    def test_ordinary_name_still_parses(self):
        ET.fromstring(self.export_lens_svg(_lens(name="Ordinary Lens")))


class TestEscapingRoundTrips(_SVGBase):
    """Escaping must be lossless: the text still reads correctly."""

    def _texts(self, svg):
        return [t.text or "" for t in ET.fromstring(svg).iter(f"{SVG_NS}text")]

    def test_name_round_trips_through_the_parser(self):
        texts = self._texts(self.export_lens_svg(_lens(name=SCRIPT_NAME)))
        self.assertTrue(any(SCRIPT_NAME in t for t in texts), texts[:3])

    def test_ampersand_name_round_trips(self):
        texts = self._texts(self.export_lens_svg(_lens(name=AMP_NAME)))
        self.assertTrue(any(AMP_NAME in t for t in texts), texts[:3])

    def test_material_round_trips(self):
        texts = self._texts(self.export_lens_svg(_lens(name="F", material=AMP_NAME)))
        self.assertTrue(any(AMP_NAME in t for t in texts), texts[:3])

    def test_unicode_name_round_trips(self):
        texts = self._texts(self.export_lens_svg(_lens(name=UNICODE_NAME)))
        self.assertTrue(any(UNICODE_NAME in t for t in texts), texts[:3])

    def test_no_text_node_is_empty(self):
        """Escaping must not swallow the value entirely."""
        texts = self._texts(self.export_lens_svg(_lens(name="Real Name")))
        self.assertTrue(any("Real Name" in t for t in texts))


class TestOrdinaryOutputUnchanged(unittest.TestCase):
    """A plain name must come out byte-for-byte as before."""

    def test_simple_name_is_not_mangled(self):
        handle, path = tempfile.mkstemp(suffix=".svg")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        SVGExporter.export_lens(_lens(name="BK7 Standard"), path)
        with open(path, encoding="utf-8") as f:
            svg = f.read()
        self.assertIn("BK7 Standard", svg)
        self.assertNotIn("&amp;amp;", svg)
        self.assertNotIn("&amp;lt;", svg)

    def test_iso_simple_name_is_not_mangled(self):
        handle, path = tempfile.mkstemp(suffix=".svg")
        os.close(handle)
        self.addCleanup(os.unlink, path)
        ISO10110Generator(_system(name="Doublet")).generate_svg(path)
        with open(path, encoding="utf-8") as f:
            svg = f.read()
        self.assertIn("Doublet", svg)
        self.assertNotIn("&amp;amp;", svg)


if __name__ == "__main__":
    unittest.main()
