"""Regression: the Performance tab must not show metrics for a lens that changed.

Cached metrics were matched to a lens by *object identity*
(``_cached_metrics_for is not active_system``). The editor edits the lens in
place, so the identity never changed: after a radius edit the tab went on
repainting the focal length and aberrations of the lens as it was **before** the
edit, with nothing on screen to say the numbers were out of date.

The nastier half is the wording. Once the cache is correctly invalidated, the
tab falls back to "Metrics not yet calculated" - which tells the user to press a
button. But they *did* press it, for this lens, moments ago; the report they were
reading is the one that just stopped describing the design in front of them.
Saying "not yet calculated" describes a state the user was never in, and is what
made the staleness invisible in the first place.
"""

import os
import sys
import unittest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QWidget

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    QWidget = None
    PYSIDE_AVAILABLE = False

if PYSIDE_AVAILABLE:
    from tests import ensure_qapp

    ensure_qapp()

from openlens.gui.tabs.performance_tab import metrics_fingerprint
from openlens.lens import Lens


def _lens(radius=60.0):
    return Lens(
        name="Crown",
        radius_of_curvature_1=radius,
        radius_of_curvature_2=-radius,
        thickness=6.0,
        diameter=30.0,
        material="N-BK7",
        refractive_index=1.5168,
    )


class TestFingerprintTracksWhatTheLensIs(unittest.TestCase):
    """The cache key has to notice an edit, and ignore a non-edit."""

    def test_an_edit_changes_the_fingerprint(self):
        lens = _lens()
        before = metrics_fingerprint(lens)

        lens.radius_of_curvature_1 = 35.0

        self.assertNotEqual(
            metrics_fingerprint(lens),
            before,
            msg="an in-place edit did not change the fingerprint, so the cache "
            "cannot tell an edited lens from an untouched one",
        )

    def test_every_optical_field_is_covered(self):
        """A hand-picked key list would leave a new field out silently."""
        lens = _lens()
        baseline = metrics_fingerprint(lens)

        fields = {
            "radius_of_curvature_2": -120.0,
            "thickness": 9.0,
            "diameter": 44.0,
            "refractive_index": 1.7847,
            "material": "SF11",
            "wavelength": 486.1,
            "coating_1": "AR broadband",
        }
        for field, value in fields.items():
            with self.subTest(field=field):
                fresh = _lens()
                setattr(fresh, field, value)
                self.assertNotEqual(metrics_fingerprint(fresh), baseline)

    def test_a_touch_without_an_optical_change_keeps_the_fingerprint(self):
        """modified_at changes on every write; it is not a design change."""
        lens = _lens()
        before = metrics_fingerprint(lens)

        lens.modified_at = "2000-01-01T00:00:00"

        self.assertEqual(
            metrics_fingerprint(lens),
            before,
            msg="a timestamp change threw the cache away, so the report would "
            "be recomputed constantly for no reason",
        )

    def test_untouched_lenses_fingerprint_equally(self):
        self.assertEqual(metrics_fingerprint(_lens()), metrics_fingerprint(_lens()))

    def test_two_different_lenses_differ(self):
        self.assertNotEqual(metrics_fingerprint(_lens(60.0)), metrics_fingerprint(_lens(35.0)))


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class _TabFixture(unittest.TestCase):
    def setUp(self):
        from openlens.gui.tabs.performance_tab import PerformanceTab
        from tests import flush_qt

        # Registered first so it runs last: the deleteLater cleanups below
        # only schedule the deletion, flush_qt delivers it while Qt lives.
        self.addCleanup(flush_qt)

        # BaseTab hands its parent to QWidget, so the stand-in has to be one.
        class _Parent(QWidget):
            def __init__(self):
                super().__init__()
                self._current_assembly = None
                self._current_lens = None
                self.status = []

            def _update_status(self, message):
                self.status.append(message)

        self.parent = _Parent()
        self.addCleanup(self.parent.deleteLater)
        self.tab = PerformanceTab(self.parent)
        self.addCleanup(self.tab.deleteLater)

    def _fake_calculate(self, text, results=None, stamp=None):
        """Populate the cache as a successful Calculate Metrics would."""
        self.tab._cached_metrics_text = text
        self.tab._cached_metrics = results if results is not None else {}
        self.tab._cached_metrics_for = self.parent._current_lens
        self.tab._cached_metrics_stamp = (
            stamp if stamp is not None else metrics_fingerprint(self.parent._current_lens)
        )

    def _shown(self):
        self.tab.refresh()
        return self.tab._perf_metrics_text.toPlainText()


class TestAnEditedLensDropsTheCache(_TabFixture):
    def setUp(self):
        super().setUp()
        self.lens = _lens()
        self.parent._current_lens = self.lens
        self._fake_calculate("Focal Length: 60.0000 mm")

    def test_the_cached_metrics_are_reported(self):
        self.assertIn("60.0000 mm", self._shown())

    def test_an_edit_stops_the_old_metrics_being_reported(self):
        self.lens.radius_of_curvature_1 = 35.0

        shown = self._shown()

        self.assertNotIn(
            "60.0000 mm",
            shown,
            msg="the tab repainted the pre-edit focal length, so the report "
            "silently describes a design the user has changed",
        )

    def test_an_edit_clears_the_cache_itself(self):
        self.lens.thickness = 11.0

        self.tab.refresh()

        self.assertIsNone(
            self.tab._cached_metrics_text,
            msg="the cache survived an edit, so it would be repainted later",
        )
        self.assertIsNone(self.tab._cached_metrics)

    def test_recalculating_after_an_edit_reports_the_new_design(self):
        self.lens.radius_of_curvature_1 = 35.0
        self.tab.refresh()

        self._fake_calculate("Focal Length: 35.0000 mm")

        self.assertIn("35.0000 mm", self._shown())

    def test_a_recalculation_is_not_immediately_discarded_as_stale(self):
        """Invalidating on refresh must not loop with its own bookkeeping."""
        self._fake_calculate("Focal Length: 35.0000 mm")

        self.tab.refresh()
        self.tab.refresh()

        self.assertIn(
            "35.0000 mm",
            self._shown(),
            msg="a fresh result was thrown away on the next refresh",
        )


class TestTheWordingTellsTheTruth(_TabFixture):
    """Invalidating correctly is only half the fix; the message must be right."""

    def setUp(self):
        super().setUp()
        self.lens = _lens()
        self.parent._current_lens = self.lens
        self._fake_calculate("Focal Length: 60.0000 mm")

    def test_an_edited_lens_is_not_reported_as_never_calculated(self):
        self.lens.radius_of_curvature_1 = 35.0

        shown = self._shown()

        self.assertNotIn(
            "not yet calculated",
            shown,
            msg="the user did calculate these metrics - for a design that has "
            "since changed. Claiming otherwise hides what happened.",
        )

    def test_an_edited_lens_says_the_numbers_no_longer_apply(self):
        self.lens.radius_of_curvature_1 = 35.0

        shown = self._shown()

        self.assertIn(
            "changed",
            shown.lower(),
            msg="the tab does not tell the user the report is out of date",
        )

    def test_a_never_calculated_lens_still_says_so(self):
        """The two states are different and must read differently."""
        self.tab._cached_metrics_text = None
        self.tab._cached_metrics_stamp = None
        self.tab._cached_metrics_for = None

        self.assertIn("not yet calculated", self._shown().lower())

    def test_switching_targets_reports_the_new_target_as_uncalculated(self):
        other = _lens(35.0)
        self.parent._current_lens = other

        shown = self._shown()

        self.assertNotIn("60.0000 mm", shown)
        self.assertIn("not yet calculated", shown.lower())


class TestRefreshIsSafeWhenNothingIsCached(_TabFixture):
    def test_no_lens_selected(self):
        self.assertIn("select a lens", self._shown().lower())

    def test_a_lens_selected_but_never_calculated(self):
        self.parent._current_lens = _lens()

        self.assertIn("not yet calculated", self._shown().lower())

    def test_refresh_after_a_stale_invalidation_keeps_the_model(self):
        """Invalidation must not unhook the tab from the model."""
        self.parent._current_lens = _lens()
        self._fake_calculate("Focal Length: 60.0000 mm", results={"focal_length": 60.0})
        self.parent._current_lens.thickness = 8.0

        self.tab.refresh()

        self.assertIs(self.tab._cached_metrics_for, self.parent._current_lens)


if __name__ == "__main__":
    unittest.main()
