"""Regression: `metadata` must be a real, persisted attribute.

The GUI stores a lens's tolerance set on ``target.metadata['tolerances']``
(see ``OpenLensWindow._sync_tolerances_to_metadata``), but neither ``Lens`` nor
``OpticalSystem`` had a ``metadata`` attribute at all - the GUI created one
dynamically, which is why the save path worked in memory and then lost
everything:

* ``Lens.to_dict()`` and ``OpticalSystem.to_dict()`` omitted ``metadata``, so
  the tolerance set never reached the database;
* ``DatabaseManager.load_all`` flattened the metadata blob into the row dict
  and then ``del``-ed the key, so a reloaded ``Lens`` had no ``metadata``
  attribute to read.

The tolerance table therefore came back empty on reopen with nothing to say
why. ``tests/test_tolerance_persistence.py`` only checked in-memory state,
which is exactly the half that worked.

These tests go through SQLite: save, then reload, then compare.
"""

import json
import os
import sqlite3
import tempfile
import unittest

from src.database import DatabaseManager
from src.gui.storage import LensStorage
from src.lens import _LENS_SERIALIZED_KEYS, Lens
from src.optical_system import _SYSTEM_SERIALIZED_KEYS, OpticalSystem

TOLERANCES = [
    {"operand": "radius", "index": 0, "surface": 1, "target": 100.0, "tolerance": 0.05},
    {"operand": "thickness", "index": 0, "target": 5.0, "tolerance": 0.01},
]


class TestMetadataIsARealAttribute(unittest.TestCase):
    """The models must declare metadata rather than have it conjured up."""

    def test_new_lens_has_an_empty_metadata_dict(self):
        lens = Lens()
        self.assertEqual(lens.metadata, {})

    def test_two_lenses_do_not_share_one_metadata_dict(self):
        """A mutable default would leak one lens's tolerances into another."""
        first, second = Lens(), Lens()
        first.metadata["tolerances"] = TOLERANCES
        self.assertEqual(second.metadata, {})

    def test_metadata_can_be_seeded_from_the_constructor(self):
        lens = Lens(metadata={"tolerances": TOLERANCES})
        self.assertEqual(lens.metadata["tolerances"], TOLERANCES)

    def test_new_system_has_an_empty_metadata_dict(self):
        system = OpticalSystem(name="System")
        self.assertEqual(system.metadata, {})

    def test_lens_to_dict_includes_metadata(self):
        lens = Lens()
        lens.metadata["tolerances"] = TOLERANCES
        self.assertEqual(lens.to_dict()["metadata"], {"tolerances": TOLERANCES})

    def test_lens_from_dict_restores_metadata(self):
        restored = Lens.from_dict({"name": "L", "metadata": {"tolerances": TOLERANCES}})
        self.assertEqual(restored.metadata["tolerances"], TOLERANCES)

    def test_lens_to_dict_returns_a_copy(self):
        """to_dict must not hand out a live reference to the model's state."""
        lens = Lens()
        exported = lens.to_dict()
        exported["metadata"]["tolerances"] = "mutated"
        self.assertEqual(lens.metadata, {})

    def test_system_to_dict_includes_metadata(self):
        system = OpticalSystem(name="System")
        system.metadata["tolerances"] = TOLERANCES
        self.assertEqual(system.to_dict()["metadata"], {"tolerances": TOLERANCES})

    def test_system_from_dict_restores_metadata(self):
        restored = OpticalSystem.from_dict({"name": "S", "metadata": {"tolerances": TOLERANCES}})
        self.assertEqual(restored.metadata["tolerances"], TOLERANCES)


class _DbCase(unittest.TestCase):
    """Each test gets a real on-disk SQLite database."""

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.path = tmp.name
        self.addCleanup(self._remove)

    def _remove(self):
        for suffix in ("", "-shm", "-wal"):
            if os.path.exists(self.path + suffix):
                os.remove(self.path + suffix)

    def _raw_metadata(self, lens_id):
        conn = sqlite3.connect(self.path)
        try:
            row = conn.execute("SELECT metadata FROM lenses WHERE id = ?", (lens_id,)).fetchone()
        finally:
            conn.close()
        return None if row is None else json.loads(row[0])

    def _load_lens(self):
        # Dispatch the way LensStorage.load_lenses does: anything that is not
        # an OpticalSystem is a Lens. Filtering on == "Lens" looks right but
        # finds nothing, because the metadata blob carries Lens.to_dict's
        # "type" ("Biconvex", "Meniscus", ...) and load_all merges it over the
        # row's "Lens" marker. That is pre-existing and harmless in
        # production; matching it here keeps this test honest about the real
        # loading path.
        for item in DatabaseManager(self.path).load_all():
            if item.get("type") != "OpticalSystem":
                return item
        self.fail("the lens did not come back from the database")


class TestMetadataSurvivesSqlite(_DbCase):
    """The half that was actually broken: save, close, reload."""

    def test_tolerances_survive_a_save_and_reload(self):
        """The user-visible symptom from the issue."""
        lens = Lens(name="With Tolerances")
        lens.metadata["tolerances"] = TOLERANCES

        DatabaseManager(self.path).save_lens(lens.to_dict())

        self.assertEqual(self._load_lens()["metadata"]["tolerances"], TOLERANCES)

    def test_metadata_is_not_nested_under_a_metadata_key(self):
        """The blob is flat; nesting it would survive a round trip only once."""
        lens = Lens(name="With Tolerances")
        lens.metadata["tolerances"] = TOLERANCES

        DatabaseManager(self.path).save_lens(lens.to_dict())

        blob = self._raw_metadata(lens.id)
        self.assertNotIn("metadata", blob, "the metadata dict was nested into itself")
        self.assertIn("tolerances", blob)

    def test_column_backed_keys_still_have_their_own_columns(self):
        """Adding metadata must not push dedicated columns into the blob."""
        lens = Lens(name="Plain", radius_of_curvature_1=77.0)
        lens.metadata["tolerances"] = TOLERANCES

        DatabaseManager(self.path).save_lens(lens.to_dict())

        blob = self._raw_metadata(lens.id)
        for column_only in ("radius_of_curvature_1", "thickness", "name", "id"):
            self.assertNotIn(column_only, blob)

    def test_reloaded_lens_has_a_metadata_attribute(self):
        """The old load path deleted the key, so the attribute did not exist."""
        lens = Lens(name="With Tolerances")
        lens.metadata["tolerances"] = TOLERANCES
        DatabaseManager(self.path).save_lens(lens.to_dict())

        loaded = Lens.from_dict(self._load_lens())

        self.assertEqual(loaded.metadata["tolerances"], TOLERANCES)

    def test_absent_metadata_stays_empty(self):
        """A lens saved without metadata must not grow one on reload.

        Asserted on the model, not on the raw row: load_all faithfully returns
        the whole persisted blob under "metadata" (that is how lens_type and
        wavelength have always survived), and from_dict is what subtracts the
        fields the model already has.
        """
        DatabaseManager(self.path).save_lens(Lens(name="Plain").to_dict())

        loaded = Lens.from_dict(self._load_lens())

        self.assertEqual(loaded.metadata, {})

    def test_pre_existing_flat_blob_still_loads(self):
        """Blobs written before metadata existed carried flat keys only."""
        DatabaseManager(self.path)  # create the schema
        conn = sqlite3.connect(self.path)
        conn.execute(
            """
            INSERT INTO lenses (id, name, radius1, radius2, thickness, material,
                                refractive_index, diameter, created_at, modified_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "old-row",
                "Old Row",
                100.0,
                -100.0,
                5.0,
                "BK7",
                1.5168,
                40.0,
                "2024-01-01T00:00:00",
                "2024-01-01T00:00:00",
                json.dumps({"lens_type": "Biconvex", "tolerances": TOLERANCES}),
            ),
        )
        conn.commit()
        conn.close()

        loaded = Lens.from_dict(self._load_lens())

        self.assertEqual(loaded.metadata["tolerances"], TOLERANCES)

    def test_legacy_flat_keys_still_reach_the_model(self):
        """Stripping must not cost the older blob keys their attributes."""
        DatabaseManager(self.path)  # create the schema
        conn = sqlite3.connect(self.path)
        conn.execute(
            """
            INSERT INTO lenses (id, name, radius1, radius2, thickness, material,
                                refractive_index, diameter, created_at, modified_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "old-row",
                "Old Row",
                100.0,
                -100.0,
                5.0,
                "N-BK7",
                1.5168,
                40.0,
                "2024-01-01T00:00:00",
                "2024-01-01T00:00:00",
                json.dumps({"type": "Meniscus", "wavelength": 550.0, "tolerances": TOLERANCES}),
            ),
        )
        conn.commit()
        conn.close()

        loaded = Lens.from_dict(self._load_lens())

        self.assertEqual(loaded.lens_type, "Meniscus")
        self.assertEqual(loaded.wavelength, 550.0)
        self.assertEqual(loaded.material, "N-BK7")
        self.assertEqual(loaded.metadata["tolerances"], TOLERANCES)

    def test_system_metadata_survives_a_save_and_reload(self):
        """Assemblies carry their own metadata column and lose it the same way."""
        db = DatabaseManager(self.path)
        system = OpticalSystem(name="System")
        system.add_lens(Lens(name="Element"))
        system.metadata["tolerances"] = TOLERANCES

        db.save_assembly(system.to_dict())

        for item in DatabaseManager(self.path).load_all():
            if item.get("type") == "OpticalSystem":
                self.assertEqual(item["metadata"]["tolerances"], TOLERANCES)
                return
        self.fail("the assembly did not come back from the database")


class TestMetadataThroughLensStorage(unittest.TestCase):
    """The GUI path: LensStorage save, then a fresh storage load."""

    def setUp(self):
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        self.path = tmp.name
        self.storage = LensStorage(self.path)

        def cleanup():
            for suffix in ("", "-shm", "-wal"):
                if os.path.exists(self.path + suffix):
                    os.remove(self.path + suffix)

        self.addCleanup(cleanup)

    def test_tolerances_survive_storage_round_trip(self):
        lens = Lens(name="Stored")
        lens.metadata["tolerances"] = TOLERANCES

        self.assertTrue(self.storage.save_lenses([lens], show_status=False))

        reopened = LensStorage(self.path).load_lenses()
        self.assertEqual(len(reopened), 1)
        self.assertEqual(reopened[0].metadata["tolerances"], TOLERANCES)


class TestSerializedKeySetsDoNotDrift(unittest.TestCase):
    """The stripping sets must track what to_dict actually emits.

    If to_dict gains a key without _LENS_SERIALIZED_KEYS gaining it, that
    field starts leaking into metadata on every reload.
    """

    def test_lens_key_set_matches_to_dict(self):
        emitted = set(Lens().to_dict())
        self.assertEqual(emitted - _LENS_SERIALIZED_KEYS, set())
        # "wavelength_nm" is accepted by from_dict but never emitted.
        self.assertEqual(_LENS_SERIALIZED_KEYS - emitted, {"wavelength_nm"})

    def test_system_key_set_matches_to_dict(self):
        emitted = set(OpticalSystem(name="S").to_dict())
        self.assertEqual(emitted - _SYSTEM_SERIALIZED_KEYS, set())


if __name__ == "__main__":
    unittest.main()
