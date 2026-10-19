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

from openlens.io.step_export import (
    STEP_DERIVED,
    STEP_TRUE,
    StepDerived,
    StepEnum,
    StepExporter,
    StepWriter,
)


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
        """Floats render unquoted, real text is quoted, markers carry syntax."""
        target = self.writer.add_entity("CARTESIAN_POINT", ["p", (0.0, 0.0, 0.0)])
        self.writer.add_entity("ADVANCED_FACE", ["Name", 1.5, target, STEP_TRUE])
        path = self._write_to_tmp()
        with open(path) as f:
            content = f.read()
        line = re.search(r"#2=ADVANCED_FACE\((.*)\);", content).group(1)
        args = [a.strip() for a in line.split(",")]
        self.assertEqual(args[0], "'Name'")
        self.assertTrue(args[1].startswith("1.5"))  # floats render 6-decimal
        self.assertEqual(args[2], f"#{int(target)}")
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

        from openlens.lens import Lens
        from openlens.optical_system import OpticalSystem

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

        from openlens.lens import Lens
        from openlens.optical_system import OpticalSystem

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

    def test_derived_and_unset_markers_render_as_syntax(self):
        """'*' (derived) and '$' (unset, Python None) are markers, not text."""
        self.writer.add_entity("SOMETHING", [STEP_DERIVED, None])
        path = self._write_to_tmp()
        with open(path) as f:
            content = f.read()
        self.assertIn("#1=SOMETHING(*,$);", content)

    def test_text_that_looks_like_a_number_is_quoted(self):
        """A name is a name: '50', 'Infinity' and 'nan' must not become numbers.

        ``float()`` parses all three, so guessing from the string turned the
        solid name into a real number and produced an unreadable entity.
        """
        for name in ("50", "Infinity", "nan", "-1", "1e3", "  50  "):
            with self.subTest(name=name):
                self.writer = StepWriter()
                self.writer.add_entity("X", [name])
                self.assertEqual(self.writer.lines[-1], f"#1=X('{name}');")

    def test_text_that_looks_like_syntax_is_quoted(self):
        """A name starting with # . * or $ is text, not a pre-written token."""
        for name in ("#3 doublet", ".T.", "*star lens", "$var"):
            with self.subTest(name=name):
                self.writer = StepWriter()
                self.writer.add_entity("X", [name])
                self.assertEqual(self.writer.lines[-1], f"#1=X('{name}');")

    def test_enum_marker_renders_verbatim(self):
        self.writer.add_entity("X", [StepEnum(".F.")])
        self.assertEqual(self.writer.lines[-1], "#1=X(.F.);")

    def test_enum_marker_rejects_text_that_is_not_an_enumeration(self):
        for value in ("T", "true", ".", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    StepEnum(value)

    def test_derived_marker_is_distinct_from_text(self):
        self.assertEqual(str(StepDerived()), "*")

    def test_backslash_is_doubled(self):
        """A backslash starts an escape in Part 21; a literal one must be ``\\\\``."""
        self.writer.add_entity("X", [r"C:\lens"])
        self.assertEqual(self.writer.lines[-1], r"#1=X('C:\\lens');")

    def test_apostrophe_and_backslash_together(self):
        self.writer.add_entity("X", ["Bob's \\ lens"])
        self.assertEqual(self.writer.lines[-1], r"#1=X('Bob''s \\ lens');")

    def test_non_ascii_text_is_encoded(self):
        """Part 21 has no raw non-ASCII; ``\\X2\\`` takes UTF-16 code units."""
        self.writer.add_entity("X", ["f=50mm \u00fc"])
        self.assertEqual(self.writer.lines[-1], r"#1=X('f=50mm \X2\00FC\X0\');")

    def test_non_bmp_text_is_encoded_as_a_surrogate_pair(self):
        self.writer.add_entity("X", ["\U0001f600"])
        self.assertEqual(self.writer.lines[-1], r"#1=X('\X2\D83DDE00\X0\');")

    def test_a_run_of_non_ascii_shares_one_directive(self):
        self.writer.add_entity("X", ["\u00fc\u00f6"])
        self.assertEqual(self.writer.lines[-1], r"#1=X('\X2\00FC00F6\X0\');")

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

        from openlens.lens import Lens
        from openlens.optical_system import OpticalSystem
        from openlens.io.step_reader import read_step_solids

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


class TestStepExporterReuse(unittest.TestCase):
    """export() must be safe to call more than once on one exporter.

    The entity buffer was created only in __init__, so a second export
    appended a fresh context and a second copy of every solid to the first
    export's lines: 48 entities after one call, 96 after two.
    """

    def setUp(self):
        from openlens.lens import Lens
        from openlens.optical_system import OpticalSystem

        self.system = OpticalSystem(name="Reuse")
        self.system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
                refractive_index=1.5,
            )
        )
        self.exporter = StepExporter(self.system)

    def _export_once(self):
        fd, path = tempfile.mkstemp(suffix=".step")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        self.exporter.export(path)
        with open(path) as f:
            return [line for line in f.read().splitlines() if line.startswith("#")]

    def test_repeated_exports_are_identical(self):
        first = self._export_once()
        second = self._export_once()
        self.assertEqual(len(first), len(second))

    def test_entity_count_does_not_grow(self):
        counts = [len(self._export_once()) for _ in range(3)]
        self.assertEqual(len(set(counts)), 1, f"entity count grew: {counts}")

    def test_solids_are_not_duplicated(self):
        lines = self._export_once()
        self.assertEqual(sum("MANIFOLD_SOLID_BREP" in line for line in lines), 1)
        self.assertEqual(sum("CLOSED_SHELL" in line for line in lines), 1)

    def test_context_entities_are_not_duplicated(self):
        lines = self._export_once()
        self.assertEqual(sum("DIRECTION" in line for line in lines), 3)

    def test_ids_are_sequential_and_unique(self):
        lines = self._export_once()
        ids = [int(line[1 : line.index("=")]) for line in lines]
        self.assertEqual(ids, list(range(1, len(ids) + 1)))

    def test_orientation_markers_are_not_quoted(self):
        """The real export must use the markers, not strings that look like them.

        A call site passing ``".T."`` as plain text would now be quoted
        (``'.T.'``) - valid Part 21 for a name, silently wrong for an
        orientation flag. Both export paths are checked: the lens solid and
        the housing tube, which carry separate call sites.
        """
        lens_content = "\n".join(self._export_once())

        tube_exporter = StepExporter()
        tube_exporter._export_tube_solid("Tube", 0.0, 5.0, 10.0, 12.0)
        tube_content = "\n".join(tube_exporter.writer.lines)

        for label, content in (("lens", lens_content), ("tube", tube_content)):
            with self.subTest(export=label):
                self.assertIn(".T.", content)
                self.assertNotIn("'.T.'", content)
                self.assertIn("(*,", content)
                self.assertNotIn("'*'", content)


class TestStepWriterTextRoundTrip(unittest.TestCase):
    """Export then read back: the reader must decode what the writer encoded.

    ``step_reader`` is the import-back check for our own writer, so it is the
    place that proves the escaping is reversible rather than merely valid.
    """

    def _round_trip(self, name):
        from openlens.io.step_reader import read_step_solids
        from openlens.lens import Lens
        from openlens.optical_system import OpticalSystem

        system = OpticalSystem(name="Escaping")
        system.add_lens(
            Lens(
                name=name,
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
            )
        )
        fd, path = tempfile.mkstemp(suffix=".step")
        os.close(fd)
        self.addCleanup(os.unlink, path)
        StepExporter(system).export(path)

        solids = read_step_solids(path)
        self.assertEqual(len(solids), 1)
        return solids[0]["name"]

    def test_non_ascii_name_round_trips(self):
        name = "Lens \u00fc \u00b5m"
        self.assertEqual(self._round_trip(name), name)

    def test_non_bmp_name_round_trips(self):
        name = "Lens \U0001f600"
        self.assertEqual(self._round_trip(name), name)

    def test_backslash_name_round_trips(self):
        name = "C:\\lens\\"
        self.assertEqual(self._round_trip(name), name)

    def test_a_literal_x2_directive_in_a_name_round_trips(self):
        """Text that looks like an encoding directive must survive as text.

        The writer doubles its backslashes, so the reader has to scan left to
        right - a ``\\X2\\...`` search anywhere in the literal would decode a
        name that never encoded anything.
        """
        name = "\\X2\\00FC\\X0\\"
        self.assertEqual(self._round_trip(name), name)


if __name__ == "__main__":
    unittest.main()
