"""#475: importers cap the file they read and reject non-finite JSON.

``ZemaxSystemImporter``, ``read_step_solids`` and ``OpticalSystem.load`` read
a whole file with no size limit, and ``load`` handed Python's ``NaN`` /
``Infinity`` extensions straight to ``from_dict``.
"""

import json
import os
import tempfile
import unittest
from unittest import mock

from openlens.export_formats import ZemaxSystemImporter
from openlens.io.step_reader import read_step_solids
from openlens.optical_system import OpticalSystem
from openlens.validation import ValidationError

_TINY_ZMX = """! a tiny but valid sequential file
SURF 0
  TYPE STANDARD
  CURV 0.0
  DISZ 0.0
"""

_TINY_STEP = """ISO-10303-21;
HEADER;
ENDSEC;
DATA;
ENDSEC;
END-ISO-10303-21;
"""


@mock.patch("openlens.validation.MAX_IMPORT_FILE_BYTES", 128)
class TestImportSizeCaps(unittest.TestCase):
    def _file(self, text, suffix):
        handle, path = tempfile.mkstemp(suffix=suffix)
        os.close(handle)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self.addCleanup(os.unlink, path)
        return path

    def test_zemax_import_rejects_a_file_over_the_cap(self):
        path = self._file(_TINY_ZMX + " " * 200, ".zmx")

        with self.assertRaises(ValidationError):
            ZemaxSystemImporter.import_system(path)

    def test_step_reader_rejects_a_file_over_the_cap(self):
        path = self._file(_TINY_STEP + " " * 200, ".step")

        with self.assertRaises(ValidationError):
            read_step_solids(path)

    def test_system_load_rejects_a_file_over_the_cap(self):
        path = self._file(json.dumps({"name": "Tiny"}) + " " * 200, ".json")

        self.assertIsNone(OpticalSystem.load(path))

    def test_a_small_file_is_still_read(self):
        path = self._file(_TINY_ZMX, ".zmx")

        system = ZemaxSystemImporter.import_system(path)

        self.assertEqual(system.name, "Imported System")


class TestNonFiniteNumbers(unittest.TestCase):
    def _load(self, payload):
        handle, path = tempfile.mkstemp(suffix=".json")
        os.close(handle)
        with open(path, "w", encoding="utf-8") as f:
            f.write(payload)
        self.addCleanup(os.unlink, path)
        return OpticalSystem.load(path)

    def test_nan_is_rejected(self):
        self.assertIsNone(self._load('{"name": "T", "thickness": NaN}'))

    def test_infinity_is_rejected(self):
        self.assertIsNone(self._load('{"name": "T", "thickness": Infinity}'))


if __name__ == "__main__":
    unittest.main()
