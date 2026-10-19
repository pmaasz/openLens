"""Regression: an assembly's lenses must not reappear in the library.

``load_all`` returned every row in ``lenses`` as a top-level ``"Lens"``, including
lenses that exist only inside an assembly. After a reload the lens lists showed::

    [('Lens','L1'), ('Lens','L2'), ('OpticalSystem','A')]

for a library that held only ``A``. A full save then tried to delete each of those
lenses, the in-use guard correctly refused, and ``delete_item`` logged the refusal
at ERROR - so every save reported one failure per assembly lens while behaving
perfectly correctly.
"""

import contextlib
import logging
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from openlens.database import DatabaseManager, LensInUseError
from openlens.lens import Lens
from openlens.optical_system import OpticalSystem


def _lens(name="L1", radius=50.0):
    return Lens(
        name=name,
        radius_of_curvature_1=radius,
        radius_of_curvature_2=-radius,
        thickness=5.0,
        diameter=25.0,
        material="N-BK7",
        refractive_index=1.5168,
    )


def _assembly(*lenses, name="A"):
    system = OpticalSystem(name=name)
    for lens in lenses:
        system.add_lens(lens)
    return system


class _DbFixture(unittest.TestCase):
    def setUp(self):
        from openlens.gui.storage import LensStorage

        handle, self.path = tempfile.mkstemp(suffix=".db")
        os.close(handle)
        os.unlink(self.path)
        self.addCleanup(lambda: Path(self.path).unlink(missing_ok=True))
        self.db = DatabaseManager(self.path)
        self.storage = LensStorage(self.path)

    def _save(self, *items):
        """Save through LensStorage, as the application does.

        Library membership is recorded there - it is the only place that knows
        which lenses belong to the library, so calling DatabaseManager directly
        would skip the very thing under test.
        """
        # library_snapshot=True mirrors the application, which always hands
        # save_lenses the complete library.
        self.storage.save_lenses(list(items), show_status=False, library_snapshot=True)

    def _kinds(self):
        # A lens row's "type" holds the lens type (Biconvex, ...), not the kind
        # of row, so identify assemblies by their elements instead.
        return ["OpticalSystem" if "elements" in item else "Lens" for item in self.db.load_all()]

    def _names(self):
        return sorted(item["name"] for item in self.db.load_all())


class TestAssemblyLensesAreNotLibraryItems(_DbFixture):
    def test_the_issue_repro(self):
        """[OpticalSystem A(L1, L2)] must reload as [A], not [L1, L2, A]."""
        self._save(_assembly(_lens("L1"), _lens("L2")))

        self.assertEqual(
            self._kinds(),
            ["OpticalSystem"],
            msg="the assembly's lenses came back as standalone library lenses",
        )

    def test_no_phantom_lens_names_appear(self):
        self._save(_assembly(_lens("L1"), _lens("L2")))

        self.assertNotIn("L1", self._names())
        self.assertNotIn("L2", self._names())

    def test_a_genuinely_standalone_lens_still_loads(self):
        self._save(_lens("Loose"))

        self.assertIn("Loose", self._names())

    def test_a_lens_in_an_assembly_and_the_library_is_still_a_library_item(self):
        """Sharing a lens between the list and an assembly is legitimate."""
        shared = _lens("Shared")
        self._save(shared, _assembly(shared, name="A"))

        self.assertIn(
            "Shared",
            self._names(),
            msg="a lens the user explicitly put in the library disappeared "
            "because an assembly also uses it",
        )
        self.assertEqual(self._kinds().count("OpticalSystem"), 1)

    def test_two_assemblies_sharing_a_lens(self):
        shared = _lens("Shared")
        self._save(_assembly(shared, name="A"), _assembly(shared, name="B"))

        self.assertEqual(sorted(self._names()), ["A", "B"])

    def test_the_assembly_still_has_its_elements(self):
        """The fix must not strip the elements out of the assembly."""
        self._save(_assembly(_lens("L1"), _lens("L2")))

        assemblies = [i for i in self.db.load_all() if i["type"] == "OpticalSystem"]
        self.assertEqual(len(assemblies), 1)
        self.assertEqual(len(assemblies[0]["elements"]), 2, msg="an assembly lost an element")

    def test_every_element_has_its_lens_data(self):
        self._save(_assembly(_lens("L1"), _lens("L2", 35.0)))

        assembly = [i for i in self.db.load_all() if i["type"] == "OpticalSystem"][0]
        radii = sorted(e["lens"]["radius_of_curvature_1"] for e in assembly["elements"])

        self.assertEqual(
            radii,
            [35.0, 50.0],
            msg="an element's lens did not resolve to its own row",
        )

    def test_an_empty_library_loads_nothing(self):
        self.assertEqual(self._db_empty_check(), [])

    def _db_empty_check(self):
        return self.db.load_all()


class TestTheSavedShapeSurvivesAReload(_DbFixture):
    def test_a_round_trip_is_stable(self):
        """Reload, save again, reload: the library must not grow."""
        system = _assembly(_lens("L1"), _lens("L2"))
        self._save(system)

        first = self._kinds()
        for item in self.db.load_all():
            if item["type"] == "OpticalSystem":
                self.db.save_assembly(item)
            else:
                self.db.save_lens(item)

        self.assertEqual(
            self._kinds(),
            first,
            msg="a save/reload cycle changed the library shape",
        )


@contextlib.contextmanager
def _failing_connection(db):
    """Make DatabaseManager._connection raise from inside delete_item.

    Lets the non-LensInUseError branch be reached for real, rather than being
    asserted about with a check that cannot fail.
    """

    class _Cursor:
        def execute(self, sql, *args):
            if sql.startswith(("SELECT", "DELETE", "UPDATE")):
                raise ValueError("simulated database failure")
            return self

    class _Conn:
        def cursor(self):
            return _Cursor()

        def execute(self, *a, **k):
            raise ValueError("simulated database failure")

    with mock.patch.object(db, "_connection", lambda: _NullContext(_Conn())):
        yield


class _NullContext:
    def __init__(self, value):
        self.value = value

    def __enter__(self):
        return self.value

    def __exit__(self, *exc):
        return False


class TestTheInUseGuardIsNotLoggedAsAFailure(_DbFixture):
    def setUp(self):
        super().setUp()
        self._save(_assembly(_lens("L1"), name="A"))
        self.lens_id = self._lens_id_in_assembly("A")

    def _lens_id_in_assembly(self, assembly_name):
        for item in self.db.load_all():
            if item["type"] == "OpticalSystem" and item["name"] == assembly_name:
                return item["elements"][0]["lens_id"]
        raise AssertionError("assembly not found")

    def _capture(self, level):
        records = []

        class _Capture(logging.Handler):
            def emit(self, record):
                records.append(record)

        handler = _Capture(level=level)
        logger = logging.getLogger("openlens.database")
        # The logger's level filters records before the handler ever sees them,
        # so capturing DEBUG means setting it outright. NOTSET (0) would leave
        # the level at NOTSET and defer to the root logger, which is WARNING -
        # and min() would compute exactly that, silently discarding the debug
        # records this is here to check.
        previous = logger.level
        logger.setLevel(level)
        logger.addHandler(handler)
        self.addCleanup(logger.removeHandler, handler)
        self.addCleanup(logger.setLevel, previous)
        return records

    def test_refusing_the_delete_still_raises(self):
        """The guard must keep working - only its logging changes."""
        with self.assertRaises(LensInUseError):
            self.db.delete_item(self.lens_id)

    def test_a_refusal_is_not_logged_at_error(self):
        errors = self._capture(logging.ERROR)

        with self.assertRaises(LensInUseError):
            self.db.delete_item(self.lens_id)

        self.assertEqual(
            [r.getMessage() for r in errors],
            [],
            "the in-use guard refusing is the guard working, and reporting it "
            "as a failure makes a correct application look broken",
        )

    def test_a_genuine_delete_failure_is_still_logged_at_error(self):
        """Downgrading the refusal must not silence real errors."""
        errors = self._capture(logging.ERROR)

        with _failing_connection(self.db):
            with self.assertRaises(ValueError):
                self.db.delete_item("anything")

        self.assertTrue(
            any("Failed to delete" in r.getMessage() for r in errors),
            "a real failure is now swallowed, so a corrupt or locked database " "fails silently",
        )

    def test_the_refusal_is_explained_at_debug(self):
        debugs = self._capture(logging.DEBUG)

        with self.assertRaises(LensInUseError):
            self.db.delete_item(self.lens_id)

        self.assertTrue(
            any("Refused" in r.getMessage() for r in debugs),
            "the refusal should still be recorded, just not as a failure",
        )


class TestReconciliationDoesNotAttemptDoomedDeletes(_DbFixture):
    def setUp(self):
        super().setUp()
        self._save(_assembly(_lens("L1"), name="A"))

    def test_the_helper_reports_the_assembly_lens(self):
        ids = self.db.lens_ids_used_by_assemblies()

        self.assertEqual(len(ids), 1)

    def test_the_helper_is_empty_without_assemblies(self):
        self._save(_lens("Loose"))

        self.assertNotIn(
            "Loose",
            self.db.lens_ids_used_by_assemblies(),
            msg="a standalone lens is not assembly-held",
        )

    def test_reconciling_the_whole_library_attempts_no_deletes(self):
        """Loading the library and saving it back must not try to delete anything."""
        items = self.storage.load_lenses()
        attempted = []
        original = self.db.delete_item

        def _record(item_id):
            attempted.append(item_id)
            return original(item_id)

        self.db.delete_item = _record
        self.storage.db = self.db
        self.storage.save_lenses(items, show_status=False, reconcile=True)

        self.assertEqual(
            attempted,
            [],
            "reconcile tried to delete an assembly's lens; the in-use guard "
            "refuses every attempt, so this is guaranteed noise",
        )

    def test_reconciling_still_removes_a_genuinely_stale_lens(self):
        """Skipping in-use lenses must not disable reconciliation."""
        stale = _lens("Stale")
        self._save(stale)
        items = self.storage.load_lenses()
        items = [i for i in items if getattr(i, "name", None) != "Stale"]

        self.storage.save_lenses(items, show_status=False, reconcile=True)

        self.assertNotIn("Stale", self._names(), msg="reconciliation stopped removing stale rows")

    def test_the_assembly_survives_reconciliation(self):
        items = self.storage.load_lenses()
        self.storage.save_lenses(items, show_status=False, reconcile=True)

        self.assertIn("A", self._names())
        self.assertEqual(len([i for i in self.db.load_all() if i["type"] == "OpticalSystem"]), 1)


class TestAllIdsStillSeesEverything(_DbFixture):
    """all_ids drives reconciliation, so it must NOT apply the library filter."""

    def test_all_ids_still_includes_assembly_lenses(self):
        self._save(_assembly(_lens("L1"), name="A"))

        ids = self.db.all_ids()

        self.assertEqual(len(ids["lenses"]), 1, "reconciliation could never see this row")
        self.assertEqual(len(ids["assemblies"]), 1)


if __name__ == "__main__":
    unittest.main()
