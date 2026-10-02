#!/usr/bin/env python3
"""
Direct coverage for the low-level STEP writer (StepWriter).

test_step_export.py / test_step_export_multi.py only exercise
StepExporter; the ISO-10303-21 text assembly itself was untested.
"""

import os
import re
import tempfile
import unittest

from src.io.step_export import StepExporter, StepWriter


class TestStepWriter(unittest.TestCase):
    """Low-level STEP file assembly"""

    def setUp(self):
        self.writer = StepWriter()

    def _write_to_tmp(self):
        fd, path = tempfile.mkstemp(suffix=".step")
        os.close(fd)
        self.addCleanup(os.unlink, path)
        with open(path, "w") as f:
            f.write(self.writer.generate())
        return path

    def test_entity_ids_sequential_from_one(self):
        """add_entity returns monotonically increasing ids starting at 1"""
        ids = [self.writer.add_entity("CARTESIAN_POINT", ["P", (0.0, 0.0, 0.0)]) for _ in range(5)]
        self.assertEqual(ids, [1, 2, 3, 4, 5])

    def test_written_file_contains_header_and_entities(self):
        """File has ISO-10303-21 header and one referenced line per entity"""
        self.writer.add_entity("CARTESIAN_POINT", ["Origin", (0.0, 0.0, 0.0)])
        path = self._write_to_tmp()
        with open(path) as f:
            content = f.read()
        self.assertIn("ISO-10303-21", content)
        self.assertIn("#1=CARTESIAN_POINT", content)

    def test_numeric_and_string_arguments_rendered(self):
        """Floats render unquoted, plain strings get quoted, refs pass through"""
        self.writer.add_entity("ADVANCED_FACE", ["Name", 1.5, "#12", ".T."])
        path = self._write_to_tmp()
        with open(path) as f:
            content = f.read()
        line = re.search(r"#1=ADVANCED_FACE\((.*)\);", content).group(1)
        args = [a.strip() for a in line.split(",")]
        self.assertEqual(args[0], "'Name'")
        self.assertTrue(args[1].startswith("1.5"))  # floats render 6-decimal
        self.assertEqual(args[2], "#12")
        self.assertEqual(args[3], ".T.")

    def test_entity_id_from_add_entity_written_as_reference(self):
        """An id returned by add_entity must serialize as ``#id``, not a real.

        Passing the pre-prefixed string "#12" instead of an id hid this: a
        bare 44 in an argument position is a real number in ISO 10303-21, so
        it severs the topology-to-geometry link.
        """
        target = self.writer.add_entity("CARTESIAN_POINT", ["origin", (0.0, 0.0, 0.0)])
        self.writer.add_entity("VERTEX_POINT", ["v", target])
        line = self.writer.lines[-1]
        self.assertEqual(line, f"#2=VERTEX_POINT('v',#{int(target)});")
        self.assertNotIn(".000000", line)

    def test_integer_valued_attribute_stays_integer(self):
        """An int that is a value, not a reference, must not become ``#int``.

        GEOMETRIC_REPRESENTATION_CONTEXT takes a dimension exponent of 3;
        treating every int as a reference would emit ``#3``.
        """
        self.writer.add_entity("GEOMETRIC_REPRESENTATION_CONTEXT", ["3D", "ctx", 3])
        self.assertEqual(
            self.writer.lines[-1], "#1=GEOMETRIC_REPRESENTATION_CONTEXT('3D','ctx',3);"
        )

    def test_booleans_render_as_step_logicals(self):
        """Python bools become .T./.F. rather than 1.000000/0.000000."""
        self.writer.add_entity("EDGE_CURVE", ["e", True, False])
        self.assertEqual(self.writer.lines[-1], "#1=EDGE_CURVE('e',.T.,.F.);")

    def test_references_inside_aggregate_are_not_quoted(self):
        """Aggregate elements follow the same rules as top-level args."""
        ref = self.writer.add_entity("FACE_BOUND", ["b", 1])
        self.writer.add_entity("CLOSED_SHELL", ["shell", [ref]])
        self.assertEqual(self.writer.lines[-1], f"#2=CLOSED_SHELL('shell',(#{int(ref)}));")

    def test_exported_file_has_no_dangling_internal_references(self):
        """Every #id in a real export must resolve to an entity in the file."""
        import tempfile as _tempfile

        from src.lens import Lens
        from src.optical_system import OpticalSystem

        system = OpticalSystem(name="Link check")
        system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
            )
        )
        fd, path = _tempfile.mkstemp(suffix=".step")
        os.close(fd)
        self.addCleanup(os.unlink, path)
        StepExporter(system).export(path)

        with open(path) as f:
            content = f.read()

        defined = {int(m) for m in re.findall(r"^#(\d+)=", content, re.M)}
        self.assertTrue(defined)
        for ref in re.findall(r"#(\d+)", content):
            self.assertIn(int(ref), defined, f"#{ref} is referenced but never defined")

    def test_exported_solid_references_its_shell(self):
        """The reported defect: MANIFOLD_SOLID_BREP took a real, not #shell."""
        import tempfile as _tempfile

        from src.lens import Lens
        from src.optical_system import OpticalSystem

        system = OpticalSystem(name="Brep")
        system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
            )
        )
        fd, path = _tempfile.mkstemp(suffix=".step")
        os.close(fd)
        self.addCleanup(os.unlink, path)
        StepExporter(system).export(path)

        with open(path) as f:
            content = f.read()

        brep = re.search(r"^#\d+=MANIFOLD_SOLID_BREP\('[^']*',(.+)\);$", content, re.M)
        self.assertIsNotNone(brep)
        self.assertTrue(brep.group(1).startswith("#"))
        shell = re.search(r"^#(\d+)=CLOSED_SHELL\('[^']*',\((.+)\)\);$", content, re.M)
        self.assertIsNotNone(shell)
        # Every face in the shell must itself be an entity reference.
        for face in shell.group(2).split(","):
            self.assertTrue(face.strip().startswith("#"), f"shell face {face!r} is not a ref")

    def test_special_tokens_pass_through(self):
        """'*' (derived), '$' (unset) are emitted verbatim"""
        self.writer.add_entity("SOMETHING", ["*", "$"])
        path = self._write_to_tmp()
        with open(path) as f:
            content = f.read()
        self.assertIn("#1=SOMETHING(*,$);", content)

    def test_apostrophe_in_literal_is_doubled(self):
        """Part 21 escapes an apostrophe by doubling it.

        A lone apostrophe closes the literal early, so the rest of the entity
        becomes malformed syntax and no reader can parse the file.
        """
        self.writer.add_entity("X", ["Bob's 50mm PCX"])
        self.assertEqual(self.writer.lines[-1], "#1=X('Bob''s 50mm PCX');")

    def test_xml_special_characters_need_no_escape(self):
        """&, < and > are literal in a Part 21 text file and stay as-is."""
        self.writer.add_entity("X", ["a & b < c > d"])
        self.assertEqual(self.writer.lines[-1], "#1=X('a & b < c > d');")

    def test_leading_quote_in_text_is_escaped_not_treated_as_syntax(self):
        """Text starting with ' is text, not a pre-quoted literal."""
        self.writer.add_entity("X", ["'quoted'"])
        self.assertEqual(self.writer.lines[-1], "#1=X('''quoted''');")

    def test_apostrophe_in_aggregate_element_is_escaped(self):
        """Aggregate elements escape like any other string."""
        self.writer.add_entity("SET", [("Bob's", 1)])
        self.assertEqual(self.writer.lines[-1], "#1=SET(('Bob''s',1));")

    def test_lens_name_with_apostrophe_round_trips_through_reader(self):
        """Export then read back: the name and its points must survive."""
        import tempfile as _tempfile

        from src.lens import Lens
        from src.optical_system import OpticalSystem
        from src.io.step_reader import read_step_solids

        name = "Bob's 50mm PCX & <optics>"
        system = OpticalSystem(name="RoundTrip")
        system.add_lens(
            Lens(
                name=name,
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
            )
        )
        fd, path = _tempfile.mkstemp(suffix=".step")
        os.close(fd)
        self.addCleanup(os.unlink, path)
        StepExporter(system).export(path)

        with open(path) as f:
            content = f.read()
        self.assertIn("'Bob''s 50mm PCX & <optics>'", content)

        solids = read_step_solids(path)
        self.assertEqual(len(solids), 1)
        self.assertEqual(solids[0]["name"], name)
        self.assertGreater(len(solids[0]["points"]), 0)

    def test_housing_part_name_with_apostrophe_is_escaped(self):
        """Housing labels are interpolated too and must escape as well."""
        exporter = StepExporter()
        self.assertIsNotNone(exporter._export_tube_solid("Bob's Spacer", 0.0, 5.0, 21.0, 25.0))
        for line in exporter.writer.lines:
            if "'" in line:
                body = line.split("(", 1)[1]
                # No literal may contain an unescaped apostrophe.
                self.assertEqual(body.count("'") % 2, 0, f"unbalanced quotes: {line}")


if __name__ == "__main__":
    unittest.main()
