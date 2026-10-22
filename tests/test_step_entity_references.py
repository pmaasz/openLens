"""Regression tests for #608: STEP entity references must be references.

``StepWriter`` has written references as ``#n`` since the ``StepRef`` marker
was introduced, but several call sites still passed raw strings: the
millimetre unit arrived as ``'#unit_mm'``, the application context as
``'#application_context'``, and the B-rep items as ``('#47')``. The entities
those names point at were never written either, so the file had a dangling
reference where its length unit should be.

These tests read the exported file the way a Part 21 reader does: text
literals are not references, and every ``#n`` outside one must be defined.
"""

import os
import re
import tempfile
import unittest

from openlens.io.step_export import StepExporter
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem

#: A Part 21 string literal, apostrophes escaped by doubling.
_STRING = re.compile(r"'(?:[^']|'')*'", re.DOTALL)
_REFERENCE = re.compile(r"#(\d+)")
_DEFINITION = re.compile(r"^#(\d+)=", re.MULTILINE)


def _defined_ids(text):
    """Ids that have an entity definition, e.g. ``#12=...``."""
    return {int(match) for match in _DEFINITION.findall(text)}


def _referenced_ids(text):
    """Ids referenced in the DATA section, ignoring text literals."""
    body = text.split("DATA;", 1)[-1]
    return {int(match) for match in _REFERENCE.findall(_STRING.sub("''", body))}


def _line_with(text, entity):
    """The DATA line for *entity* (complex entities included)."""
    for line in text.splitlines():
        if line.startswith("#") and entity in line:
            return line
    return None


def _arguments(line):
    """Everything after an instance's own ``#n=``, i.e. its arguments."""
    return line.split("=", 1)[-1]


class StepEntityReferenceTest(unittest.TestCase):
    """Common export fixture."""

    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".step")
        os.close(handle)
        self.addCleanup(lambda: os.path.exists(self.path) and os.unlink(self.path))

    def export(self, target):
        StepExporter(target).export(self.path)
        with open(self.path, "r", encoding="utf-8") as handle:
            return handle.read()


class TestReferencesResolve(StepEntityReferenceTest):
    """Every reference in the file must point at a written entity."""

    def test_a_single_lens_has_no_dangling_references(self):
        text = self.export(Lens())

        missing = _referenced_ids(text) - _defined_ids(text)

        self.assertEqual(missing, set(), f"dangling STEP references: {sorted(missing)}")

    def test_a_system_has_no_dangling_references(self):
        system = OpticalSystem(name="Doublet")
        system.add_lens(Lens(thickness=3.0))
        system.add_lens(Lens(thickness=2.0, radius_of_curvature_1=-100.0))

        text = self.export(system)

        missing = _referenced_ids(text) - _defined_ids(text)

        self.assertEqual(missing, set(), f"dangling STEP references: {sorted(missing)}")

    def test_no_reference_is_written_as_quoted_text(self):
        """A reference in a text literal is the bug this issue is about."""
        text = self.export(Lens())

        body = text.split("DATA;", 1)[-1]
        quoted_references = [
            literal for literal in _STRING.findall(body) if _REFERENCE.search(literal)
        ]

        self.assertEqual(quoted_references, [], "'#n' written as text instead of a reference")

    def test_the_brep_shape_lists_the_solids_as_references(self):
        text = self.export(Lens())

        line = _line_with(text, "ADVANCED_BREP_SHAPE_REPRESENTATION(")
        self.assertIsNotNone(line)
        # The items aggregate is the only "(#..)" group; the context after it
        # is a bare reference.
        items = re.search(r"\(#\d+(?:,#\d+)*\)", _arguments(line))
        self.assertIsNotNone(items, line)
        for entity_id in _REFERENCE.findall(items.group(0)):
            self.assertIn(f"#{entity_id}=MANIFOLD_SOLID_BREP", text)


class TestContextEntities(StepEntityReferenceTest):
    """The references name entities that the file actually defines."""

    def test_the_millimetre_length_unit_is_written(self):
        text = self.export(Lens())

        self.assertIn("SI_UNIT(.MILLI.,.METRE.)", text)
        self.assertIn("LENGTH_UNIT()", text)
        self.assertIn("NAMED_UNIT(*)", text)
        self.assertNotIn("#unit_mm", text)

    def test_the_application_context_is_written(self):
        text = self.export(Lens())

        self.assertIn("APPLICATION_CONTEXT(", text)
        self.assertNotIn("#application_context", text)

    def test_the_product_context_points_at_the_application_context(self):
        text = self.export(Lens())

        line = _line_with(text, "PRODUCT_CONTEXT(")
        self.assertIsNotNone(line)
        references = _REFERENCE.findall(_STRING.sub("''", _arguments(line)))
        self.assertTrue(references, f"PRODUCT_CONTEXT has no reference: {line}")
        context_id = references[0]
        self.assertIn(f"#{context_id}=APPLICATION_CONTEXT(", text)

    def test_the_geometric_context_assigns_units_and_uncertainty(self):
        """Without this, nothing in the file says what a length unit is."""
        text = self.export(Lens())

        line = _line_with(text, "GEOMETRIC_REPRESENTATION_CONTEXT(")
        self.assertIsNotNone(line)
        self.assertIn("GLOBAL_UNIT_ASSIGNED_CONTEXT((#", line)
        self.assertIn("GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#", line)
        self.assertIn("REPRESENTATION_CONTEXT('','')", line)

        unit_id = re.search(r"GLOBAL_UNIT_ASSIGNED_CONTEXT\(\(#(\d+)\)\)", line).group(1)
        self.assertIn("SI_UNIT(.MILLI.,.METRE.)", _line_with(text, f"#{unit_id}="))

    def test_the_uncertainty_is_a_length_measure_of_the_unit(self):
        text = self.export(Lens())

        line = _line_with(text, "UNCERTAINTY_MEASURE_WITH_UNIT(")
        self.assertIsNotNone(line)
        self.assertIn("LENGTH_MEASURE(", line)

        references = re.findall(r"#(\d+)", _STRING.sub("''", _arguments(line)))
        self.assertTrue(references, f"the uncertainty names no unit: {line}")
        unit_id = references[0]
        self.assertIn("SI_UNIT(.MILLI.,.METRE.)", _line_with(text, f"#{unit_id}="))


class TestTextThatLooksLikeAReference(StepEntityReferenceTest):
    """A name is text, even when it is spelled like an entity id."""

    def test_a_lens_name_with_a_hash_is_not_a_reference(self):
        text = self.export(Lens(name="#12 doublet"))

        self.assertIn("'#12 doublet'", text)
        self.assertEqual(_referenced_ids(text) - _defined_ids(text), set())


if __name__ == "__main__":
    unittest.main()
