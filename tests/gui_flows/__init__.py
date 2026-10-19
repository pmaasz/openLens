"""The GUI flow QA suite runs under pytest, not unittest discovery.

Its modules are pytest-style and share fixtures from ``conftest.py``, which
imports pytest at module level. unittest discovery imports every ``test*.py``
it finds, so ``python3 -m unittest discover -s tests -t .`` reported a loader
error for all six flow modules whenever pytest was not installed.

Defining ``load_tests`` makes discovery stop at this package and contribute
nothing; the suite still runs through its own command,
``python3 -m pytest tests/gui_flows -v`` (pytest ignores ``load_tests``).
"""

import unittest


def load_tests(loader, standard_tests, pattern):
    """Contribute no tests to unittest discovery; pytest owns this suite."""
    return unittest.TestSuite()
