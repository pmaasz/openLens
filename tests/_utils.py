"""Shared helpers for the OpenLens test suite."""

import os
import unittest

#: Set OPENLENS_SKIP_SLOW=1 to skip slow/integration tests (e.g. quick
#: inner-loop runs). By default every test executes.
SKIP_SLOW = os.environ.get('OPENLENS_SKIP_SLOW') == '1'

skip_slow = unittest.skipIf(SKIP_SLOW, "slow/integration test (OPENLENS_SKIP_SLOW=1)")
