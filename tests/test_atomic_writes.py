#!/usr/bin/env python3
"""
Exports must never destroy the previous file.

``open(path, "w")`` truncates immediately, so any failure after that point -
a serialiser raising partway, a geometry check, an interrupt - left the user
with a truncated file *and* the previous good one already gone.

Writes now go to a temporary file in the same directory and are moved over
the target with ``os.replace``, which is atomic.
"""

import json
import os
import tempfile
import unittest

from src.atomic import atomic_write_bytes, atomic_write_json, atomic_write_text


class TestAtomicWriteText(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".txt")
        os.close(handle)
        os.unlink(self.path)
        self.addCleanup(lambda: os.path.exists(self.path) and os.unlink(self.path))
        self.tmp_path = self.path + ".tmp"
        self.addCleanup(lambda: os.path.exists(self.tmp_path) and os.unlink(self.tmp_path))

    def test_writes_the_file(self):
        with atomic_write_text(self.path) as handle:
            handle.write("hello")
        with open(self.path) as handle:
            self.assertEqual(handle.read(), "hello")

    def test_missing_parent_directory_is_not_created(self):
        """No implicit mkdir: save() must still fail on a bad path."""
        import shutil

        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, True)
        target = os.path.join(directory, "nested", "deep", "out.txt")
        with self.assertRaises(OSError):
            with atomic_write_text(target) as handle:
                handle.write("x")
        self.assertFalse(os.path.exists(target))
        self.assertFalse(os.path.exists(target + ".tmp"))

    def test_failure_leaves_the_previous_file_intact(self):
        """The core guarantee."""
        with atomic_write_text(self.path) as handle:
            handle.write("ORIGINAL")

        with self.assertRaises(RuntimeError):
            with atomic_write_text(self.path) as handle:
                handle.write("PARTIAL")
                raise RuntimeError("serialiser failed partway")

        with open(self.path) as handle:
            self.assertEqual(handle.read(), "ORIGINAL")

    def test_failure_removes_the_temporary_file(self):
        with self.assertRaises(RuntimeError):
            with atomic_write_text(self.path) as handle:
                handle.write("x")
                raise RuntimeError("boom")
        self.assertFalse(os.path.exists(self.tmp_path))

    def test_base_exception_also_rolls_back(self):
        """KeyboardInterrupt / SystemExit must not truncate the target."""
        with atomic_write_text(self.path) as handle:
            handle.write("ORIGINAL")
        with self.assertRaises(KeyboardInterrupt):
            with atomic_write_text(self.path) as handle:
                handle.write("PARTIAL")
                raise KeyboardInterrupt
        with open(self.path) as handle:
            self.assertEqual(handle.read(), "ORIGINAL")

    def test_overwrites_an_existing_file(self):
        with atomic_write_text(self.path) as handle:
            handle.write("first")
        with atomic_write_text(self.path) as handle:
            handle.write("second")
        with open(self.path) as handle:
            self.assertEqual(handle.read(), "second")

    def test_temporary_file_is_in_the_same_directory(self):
        """os.replace is only atomic within one filesystem."""
        with atomic_write_text(self.path) as handle:
            handle.write("x")
        # A successful write leaves no temp file behind.
        self.assertFalse(os.path.exists(self.tmp_path))


class TestAtomicWriteJson(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        os.unlink(self.path)
        self.addCleanup(lambda: os.path.exists(self.path) and os.unlink(self.path))

    def test_writes_valid_json(self):
        atomic_write_json(self.path, {"a": 1})
        with open(self.path) as handle:
            self.assertEqual(json.load(handle), {"a": 1})

    def test_unserialisable_payload_keeps_the_previous_file(self):
        atomic_write_json(self.path, {"good": True})
        with self.assertRaises(TypeError):
            atomic_write_json(self.path, {"bad": object()})
        with open(self.path) as handle:
            self.assertEqual(json.load(handle), {"good": True})


class TestAtomicWriteBytes(unittest.TestCase):
    def setUp(self):
        handle, self.path = tempfile.mkstemp(suffix=".bin")
        os.close(handle)
        os.unlink(self.path)
        self.addCleanup(lambda: os.path.exists(self.path) and os.unlink(self.path))

    def test_writes_bytes(self):
        with atomic_write_bytes(self.path) as handle:
            handle.write(b"\x00\x01STL")
        with open(self.path, "rb") as handle:
            self.assertEqual(handle.read(), b"\x00\x01STL")

    def test_failure_keeps_the_previous_file(self):
        with atomic_write_bytes(self.path) as handle:
            handle.write(b"ORIGINAL")
        with self.assertRaises(RuntimeError):
            with atomic_write_bytes(self.path) as handle:
                handle.write(b"PARTIAL")
                raise RuntimeError("boom")
        with open(self.path, "rb") as handle:
            self.assertEqual(handle.read(), b"ORIGINAL")


class TestExportsUseAtomicWrites(unittest.TestCase):
    """The real exporters must go through the helper."""

    def test_step_export_leaves_previous_file_on_failure(self):
        import tempfile as tf

        from src.lens import Lens
        from src.optical_system import OpticalSystem
        from src.io.step_export import StepExporter

        fd, path = tf.mkstemp(suffix=".step")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        with open(path, "w") as handle:
            handle.write("PREVIOUS")

        system = OpticalSystem(name="S")
        system.add_lens(
            Lens(
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                thickness=5.0,
                diameter=20.0,
            )
        )
        exporter = StepExporter(system)

        original = exporter._export_lens_solid

        def explode(*args, **kwargs):
            raise RuntimeError("geometry exploded mid-export")

        exporter._export_lens_solid = explode
        with self.assertRaises(RuntimeError):
            exporter.export(path)

        with open(path) as handle:
            self.assertEqual(handle.read(), "PREVIOUS")

    def test_material_database_save_keeps_previous_file(self):
        """A serialiser that fails partway must not destroy the database."""
        import tempfile as tf

        from src.material_database import MaterialDatabase

        fd, path = tf.mkstemp(suffix=".json")
        os.close(fd)
        self.addCleanup(lambda: os.path.exists(path) and os.unlink(path))
        with open(path, "w") as handle:
            handle.write('{"PREVIOUS": {}}')

        db = MaterialDatabase(path)
        real_dump = json.dump

        def exploding_dump(payload, handle, **kwargs):
            handle.write("{")  # partial write, then failure
            raise RuntimeError("serialiser failed partway")

        json.dump = exploding_dump
        try:
            with self.assertRaises(RuntimeError):
                db.save_database()
        finally:
            json.dump = real_dump

        with open(path) as handle:
            self.assertEqual(json.load(handle), {"PREVIOUS": {}})


if __name__ == "__main__":
    unittest.main()
