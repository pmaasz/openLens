"""Tests for tolerance-set persistence.

Regression cover for #326: ``_save_to_database`` stamped
``metadata['tolerances']`` onto whichever model was current, and nothing ever
read it back. Because ``_tol_operands`` is a single list on the window, the
result was that one lens's tolerance set was written into every other lens's
metadata, while the real set vanished on reopen and the UI reported an empty
table as if nothing had been configured.
"""

import unittest

import openlens
from openlens import OpenLensWindow
from src.lens import Lens
from src.tolerancing import (
    ToleranceOperand,
    ToleranceType,
    deserialize_operands,
    serialize_operands,
)


def _lens(name):
    return Lens(
        name=name,
        radius_of_curvature_1=100.0,
        radius_of_curvature_2=-100.0,
        thickness=5.0,
        diameter=25.0,
        refractive_index=1.5168,
    )


def _operands():
    return [
        ToleranceOperand(0, ToleranceType.RADIUS_1, -0.1, 0.1),
        ToleranceOperand(0, ToleranceType.THICKNESS, -0.05, 0.05, distribution="gaussian"),
        ToleranceOperand(1, ToleranceType.DECENTER_Y, -0.02, 0.02, std_dev=0.01, surface=2),
    ]


class TestOperandSerialization(unittest.TestCase):
    def test_round_trip_preserves_every_field(self):
        """Serialising then deserialising must be lossless."""
        original = _operands()
        self.assertEqual(deserialize_operands(serialize_operands(original)), original)

    def test_serialised_form_is_json_safe(self):
        """The stored form must be plain data, not enum members."""
        import json

        encoded = json.dumps(serialize_operands(_operands()))
        self.assertIn('"type": "Radius 1"', encoded)

    def test_missing_metadata_yields_no_operands(self):
        """A model with no stored tolerances loads an empty set."""
        self.assertEqual(deserialize_operands(None), [])

    def test_non_list_metadata_is_ignored(self):
        """Corrupt metadata must not raise out of a GUI refresh."""
        self.assertEqual(deserialize_operands({"not": "a list"}), [])
        self.assertEqual(deserialize_operands("garbage"), [])

    def test_unknown_type_is_skipped(self):
        """An operand whose type this build does not know is dropped."""
        raw = [{"element_index": 0, "type": "Warp Factor", "min_val": -1, "max_val": 1}]
        self.assertEqual(deserialize_operands(raw), [])

    def test_broken_entries_do_not_discard_the_good_ones(self):
        """One bad entry must not lose the rest of the tolerance set."""
        raw = [
            "not a dict",
            {"element_index": 0, "type": "Nope", "min_val": 0, "max_val": 1},
            {"type": "Radius 1", "min_val": "abc", "max_val": 1},
            {"element_index": 0, "type": "Radius 1", "min_val": -0.1, "max_val": 0.1},
        ]
        recovered = deserialize_operands(raw)
        self.assertEqual(len(recovered), 1)
        self.assertEqual(recovered[0].param_type, ToleranceType.RADIUS_1)

    def test_unknown_distribution_falls_back_to_uniform(self):
        """An unusable distribution must not reach generate_value()."""
        raw = [
            {
                "element_index": 0,
                "type": "Radius 1",
                "min_val": -0.1,
                "max_val": 0.1,
                "distribution": "cauchy",
            }
        ]
        self.assertEqual(deserialize_operands(raw)[0].distribution, "uniform")


class _BareWindow:
    """Real OpenLensWindow persistence methods, without the Qt ``__init__``.

    ``__new__`` skips the widget construction (which needs a QApplication and a
    startup dialog) while keeping the actual methods under test, so these
    tests exercise shipped code rather than a copy of it.
    """

    def __init__(self):
        window = OpenLensWindow.__new__(OpenLensWindow)
        window._tol_operands = []
        window._tol_operands_target = None
        window._current_lens = None
        window._current_assembly = None
        self._window = window

    def _use_tolerances_for(self, target):
        self._window._use_tolerances_for(target)

    def _sync_tolerances_to_metadata(self, target=None):
        self._window._sync_tolerances_to_metadata(target)

    @property
    def _tol_operands(self):
        return self._window._tol_operands

    @_tol_operands.setter
    def _tol_operands(self, value):
        self._window._tol_operands = value

    @property
    def _current_lens(self):
        return self._window._current_lens

    @_current_lens.setter
    def _current_lens(self, value):
        self._window._current_lens = value


class TestToleranceOwnership(unittest.TestCase):
    """The core of #326: a set must follow the model it was built for."""

    def setUp(self):
        self.window = _BareWindow()
        self.a = _lens("A")
        self.b = _lens("B")

    def test_saved_set_is_restored_on_reopen(self):
        """build -> save -> reopen must show the same operands."""
        self.window._current_lens = self.a
        self.window._use_tolerances_for(self.a)
        self.window._tol_operands = _operands()
        self.window._sync_tolerances_to_metadata()

        reopened = _BareWindow()
        reopened._use_tolerances_for(self.a)
        self.assertEqual(reopened._tol_operands, _operands())

    def test_set_is_not_leaked_into_other_models(self):
        """Editing one lens must not stamp its set onto another."""
        self.window._current_lens = self.a
        self.window._use_tolerances_for(self.a)
        self.window._tol_operands = _operands()

        self.window._current_lens = self.b
        self.window._use_tolerances_for(self.b)

        self.assertNotIn("tolerances", getattr(self.b, "metadata", {}) or {})
        self.assertEqual(self.window._tol_operands, [])

    def test_each_model_keeps_its_own_set(self):
        """Two lenses with different sets must both round-trip."""
        set_a = [ToleranceOperand(0, ToleranceType.RADIUS_1, -0.1, 0.1)]
        set_b = [ToleranceOperand(0, ToleranceType.THICKNESS, -0.05, 0.05)]

        self.window._current_lens = self.a
        self.window._use_tolerances_for(self.a)
        self.window._tol_operands = set_a
        self.window._sync_tolerances_to_metadata()

        self.window._current_lens = self.b
        self.window._use_tolerances_for(self.b)
        self.window._tol_operands = set_b
        self.window._sync_tolerances_to_metadata()

        self.assertEqual(deserialize_operands(self.a.metadata["tolerances"]), set_a)
        self.assertEqual(deserialize_operands(self.b.metadata["tolerances"]), set_b)

    def test_switching_back_restores_the_first_set(self):
        """Re-selecting A must bring A's operands back, not B's."""
        set_a = [ToleranceOperand(0, ToleranceType.RADIUS_1, -0.1, 0.1)]
        set_b = [ToleranceOperand(0, ToleranceType.DECENTER_X, -0.02, 0.02)]

        self.window._use_tolerances_for(self.a)
        self.window._tol_operands = set_a
        self.window._use_tolerances_for(self.b)
        self.window._tol_operands = set_b
        self.window._use_tolerances_for(self.a)

        self.assertEqual(self.window._tol_operands, set_a)

    def test_unstamped_edits_are_kept_when_leaving_a_model(self):
        """Edits made since the last save must not be lost on a switch."""
        edited = [ToleranceOperand(0, ToleranceType.TILT_X, -0.3, 0.3)]
        self.window._use_tolerances_for(self.a)
        self.window._tol_operands = edited

        self.window._use_tolerances_for(self.b)

        # Switching away stamped the in-memory list onto A before leaving.
        self.assertEqual(deserialize_operands(self.a.metadata["tolerances"]), edited)

    def test_refreshing_the_same_model_keeps_in_memory_edits(self):
        """_update_all_tabs runs on every change; it must not reset the table."""
        edits = [ToleranceOperand(0, ToleranceType.WEDGE, -1.0, 1.0)]
        self.window._use_tolerances_for(self.a)
        self.window._tol_operands = edits

        # Same target again, as _update_all_tabs would do.
        self.window._use_tolerances_for(self.a)
        self.assertEqual(self.window._tol_operands, edits)

    def test_model_without_stored_tolerances_loads_empty(self):
        """A never-configured model must load an empty set, not another model's."""
        self.window._use_tolerances_for(self.a)
        self.window._tol_operands = _operands()
        self.window._use_tolerances_for(self.b)
        self.assertEqual(self.window._tol_operands, [])


if __name__ == "__main__":
    unittest.main()
