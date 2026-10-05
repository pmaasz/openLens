#!/usr/bin/env python3
"""
The assembly tab's empty-lens-list retry must be bounded.

refresh_lens_list ended with

    if self._assembly_lens_list.count() == 0:
        QTimer.singleShot(100, self.refresh_lens_list)

No retry cap, no cancellation, no give-up state. openlens.py sets
self._lenses = [] on the database-load failure path, so a library that never
fills woke the Qt event loop 10x/second for the entire session: measurable
constant CPU, and it hid the real problem behind a permanently empty list.

Verified before the fix: 25 invocations in 1.2 s with an empty library, still
scheduling more, no placeholder.

The retry is now capped, the timer is held so it can be cancelled, exhausting
the budget shows a non-selectable placeholder naming the likely cause, and
the counter resets on success.
"""

import os
import sys
import unittest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QListWidgetItem

    PYSIDE_AVAILABLE = True
except ImportError as _e:  # pragma: no cover - environment guard
    QTimer = None
    QApplication = None
    QListWidgetItem = None
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = _e

from src.lens import Lens

if PYSIDE_AVAILABLE:
    _app = QApplication.instance()
    if not _app:
        _app = QApplication(sys.argv)


class _Parent:
    def __init__(self, lenses=None):
        self._lenses = lenses if lenses is not None else []
        self.statuses = []

    def _update_status(self, message):
        self.statuses.append(message)


PLACEHOLDER = "(no lenses loaded - check the lens database)"


def _lens(name):
    return Lens(
        name=name,
        radius_of_curvature_1=50.0,
        radius_of_curvature_2=-50.0,
        thickness=5.0,
        diameter=25.0,
        refractive_index=1.5,
    )


def _pump(ms):
    """Spin the event loop for `ms` so real timers can fire."""
    QTimer.singleShot(ms, _app.quit)
    _app.exec()
    _app.processEvents()


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class _AssemblyTabFixture(unittest.TestCase):
    def setUp(self):
        from src.gui.tabs.assembly_tab import AssemblyTab

        self.tab = AssemblyTab()
        self.tab._parent = _Parent()
        self.addCleanup(self.tab.deleteLater)

    def tearDown(self):
        self.tab._cancel_lens_list_retry()


class TestRetryIsBounded(_AssemblyTabFixture):
    def test_retries_stop_at_the_cap(self):
        """Regression: unbounded, 10x/second, for the whole session."""
        self.tab.LENS_LIST_MAX_RETRIES = 3
        self.tab.refresh_lens_list()
        _pump(400)
        self.assertLessEqual(self.tab._lens_list_retries, self.tab.LENS_LIST_MAX_RETRIES)
        self.assertIsNone(self.tab._lens_list_retry_timer)

    def test_no_further_invocations_once_capped(self):
        self.tab.LENS_LIST_MAX_RETRIES = 2
        self.tab.refresh_lens_list()
        _pump(200)
        before = self.tab._lens_list_retries
        _pump(400)
        self.assertEqual(self.tab._lens_list_retries, before)

    def test_timer_is_held_so_it_can_be_cancelled(self):
        self.tab.refresh_lens_list()
        self.assertIsNotNone(self.tab._lens_list_retry_timer)
        self.assertTrue(self.tab._lens_list_retry_timer.isActive())

    def test_cancel_stops_the_timer(self):
        self.tab.refresh_lens_list()
        self.tab._cancel_lens_list_retry()
        self.assertIsNone(self.tab._lens_list_retry_timer)
        self.assertEqual(self.tab._lens_list_retries, 0)

    def test_timer_is_not_recreated_on_every_attempt(self):
        """A fresh singleShot per attempt is what leaked; one timer is reused."""
        self.tab.refresh_lens_list()
        first = self.tab._lens_list_retry_timer
        _pump(150)
        if self.tab._lens_list_retry_timer is not None:
            self.assertIs(self.tab._lens_list_retry_timer, first)
        self.assertIsNotNone(first)


class TestPlaceholder(_AssemblyTabFixture):
    def test_placeholder_appears_after_the_cap(self):
        """Regression: the user only ever saw an unexplained empty list."""
        self.tab.LENS_LIST_MAX_RETRIES = 2
        self.tab.refresh_lens_list()
        _pump(400)
        self.assertEqual(self.tab._assembly_lens_list.count(), 1)
        self.assertEqual(self.tab._assembly_lens_list.item(0).text(), PLACEHOLDER)

    def test_placeholder_is_not_selectable(self):
        self.tab.LENS_LIST_MAX_RETRIES = 1
        self.tab.refresh_lens_list()
        _pump(300)
        item = self.tab._assembly_lens_list.item(0)
        selectable = QListWidgetItem.flags(item).ItemIsSelectable
        self.assertFalse(bool(item.flags() & selectable))

    def test_placeholder_does_not_reappear_once_real_lenses_load(self):
        self.tab.LENS_LIST_MAX_RETRIES = 1
        self.tab.refresh_lens_list()
        _pump(300)
        self.assertEqual(self.tab._assembly_lens_list.count(), 1)

        self.tab._parent._lenses = [_lens("Real Lens")]
        self.tab.refresh_lens_list()
        self.assertEqual(self.tab._assembly_lens_list.count(), 1)
        self.assertEqual(self.tab._assembly_lens_list.item(0).text(), "Real Lens")


class TestNormalOperationUnaffected(_AssemblyTabFixture):
    def test_populated_library_lists_every_lens(self):
        self.tab._parent._lenses = [_lens("A"), _lens("B"), _lens("C")]
        self.tab.refresh_lens_list()
        names = [self.tab._assembly_lens_list.item(i).text() for i in range(3)]
        self.assertEqual(names, ["A", "B", "C"])

    def test_no_placeholder_when_lenses_exist(self):
        self.tab._parent._lenses = [_lens("A")]
        self.tab.refresh_lens_list()
        self.assertNotIn(
            PLACEHOLDER,
            [
                self.tab._assembly_lens_list.item(i).text()
                for i in range(self.tab._assembly_lens_list.count())
            ],
        )

    def test_no_timer_is_scheduled_when_lenses_exist(self):
        self.tab._parent._lenses = [_lens("A")]
        self.tab.refresh_lens_list()
        self.assertIsNone(self.tab._lens_list_retry_timer)

    def test_counter_resets_on_success(self):
        """A later genuine reload must be retried normally."""
        self.tab._parent._lenses = [_lens("A")]
        self.tab.refresh_lens_list()
        self.assertEqual(self.tab._lens_list_retries, 0)

    def test_empty_parent_attribute_is_tolerated(self):
        class Bare:
            def _update_status(self, message):
                pass

        self.tab._parent = Bare()
        self.tab.refresh_lens_list()
        self.assertEqual(self.tab._assembly_lens_list.count(), 0)

    def test_repeated_refresh_does_not_accumulate_timers(self):
        self.tab._parent._lenses = [_lens("A")]
        for _ in range(10):
            self.tab.refresh_lens_list()
        self.assertIsNone(self.tab._lens_list_retry_timer)
        self.assertEqual(self.tab._assembly_lens_list.count(), 1)


if __name__ == "__main__":
    unittest.main()
