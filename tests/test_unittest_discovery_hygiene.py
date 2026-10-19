"""#480: unittest discovery must not break on the pytest-only GUI flow suite.

Each module in ``tests/gui_flows`` imports ``conftest``, which imports pytest
at module level, so ``python3 -m unittest discover -s tests -t .`` reported a
loader error for every one of them whenever pytest was not installed. The
package's ``load_tests`` now stops discovery before it imports them.
"""

import os
import subprocess
import sys
import textwrap
import unittest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Blocks pytest so the probe behaves like a machine without it installed, even
# when this test itself runs under pytest.
_PROBE = textwrap.dedent("""
    import io
    import sys
    import unittest


    class _BlockPytest:
        def find_spec(self, name, path=None, target=None):
            if name == "pytest" or name.startswith("pytest."):
                raise ImportError("pytest is blocked for this probe")
            return None


    sys.meta_path.insert(0, _BlockPytest())

    suite = unittest.TestLoader().discover(
        "tests", top_level_dir=".", pattern="test_lens_editor_flow.py"
    )
    result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
    if result.errors:
        for test, traceback in result.errors:
            print(test.id())
            print(traceback)
        raise SystemExit(1)
    raise SystemExit(0)
    """)


class TestGuiFlowsDiscovery(unittest.TestCase):
    def test_unittest_discovery_does_not_load_gui_flows_without_pytest(self):
        result = subprocess.run(
            [sys.executable, "-c", _PROBE],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
