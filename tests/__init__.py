"""Tests package for openLens.

The test run must never write the developer's real user data. Two defaults are
now per-user files: the SQLite library and the material catalog. A number of
tests construct ``MaterialDatabase()`` (or ``LensStorage()``) with no path and
then add material, and before this guard those writes landed in the checkout's
``data/materials.json`` - which is how ``TEST_GLASS`` and friends ended up in a
real catalog.

``setdefault`` rather than assignment: an explicit override from the developer
or CI still wins.
"""

import atexit
import os
import shutil
import tempfile
from pathlib import Path

_TEST_DATA_DIR = Path(tempfile.mkdtemp(prefix="openlens-tests-"))

os.environ.setdefault("OPENLENS_DATA_DIR", str(_TEST_DATA_DIR))
os.environ.setdefault("OPENLENS_MATERIALS_PATH", str(_TEST_DATA_DIR / "materials.json"))

atexit.register(shutil.rmtree, str(_TEST_DATA_DIR), True)
