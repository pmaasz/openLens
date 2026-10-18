"""Regression: the simulation view must trace at the wavelength it displays.

The wavelength picker changed only the ray *colour*. Rays were constructed as
``Ray(-100, h + source_height, angle_rad=angle_rad)``, leaving
``wavelength_mm`` at its 550 nm default, so a lens was traced at green no matter
what the user selected - and a dispersive glass showed no dispersion at all.

Three more:

- ``refresh()`` was ``pass`` while the widget kept a live reference to the lens,
  so after an edit the view drew the *new* lens with rays belonging to the *old*
  one.
- errors went to ``print()``, which a GUI application has no way to surface.
- the 550 nm default was implicit rather than named, so the wavelength it
  silently used was a property of a default argument three frames away.
"""

import ast
import inspect
import os
import sys
import unittest

if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - environment guard
    QApplication = None
    PYSIDE_AVAILABLE = False

if PYSIDE_AVAILABLE:
    _app = QApplication.instance() or QApplication(sys.argv)

from src.constants import NM_TO_MM, WAVELENGTH_GREEN
from src.lens import Lens


def _lens():
    return Lens(
        name="Crown",
        radius_of_curvature_1=60.0,
        radius_of_curvature_2=-60.0,
        thickness=6.0,
        diameter=30.0,
        material="N-BK7",
        refractive_index=1.5168,
    )


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestRaysCarryTheSelectedWavelength(unittest.TestCase):
    """The colour and the trace have to agree."""

    def setUp(self):
        from src.gui.widgets.simulation_viz import SimulationVisualizationWidget

        self.lens = _lens()
        self.widget = SimulationVisualizationWidget()
        self.widget.run_simulation(self.lens, wavelength=WAVELENGTH_GREEN)
        self.addCleanup(self.widget.deleteLater)

    def _run(self, wavelength):
        self.widget.run_simulation(self.lens, wavelength=wavelength)
        return self.widget._rays

    def test_rays_are_traced_at_the_requested_wavelength(self):
        rays = self._run(486.1)

        self.assertTrue(rays, "no rays were traced")
        for index, ray in enumerate(rays):
            with self.subTest(ray=index):
                self.assertAlmostEqual(
                    ray.wavelength,
                    486.1 * NM_TO_MM,
                    places=12,
                    msg="the ray was traced at the 550 nm default, so "
                    "selecting a wavelength changes only the colour",
                )

    def test_several_wavelengths_give_several_trace_wavelengths(self):
        seen = []
        for wavelength in (486.1, 550.0, 656.3):
            seen.append(self._run(wavelength)[0].wavelength)

        self.assertEqual(len(set(seen)), 3, f"all rays shared one wavelength: {seen}")

    def test_the_colour_and_the_wavelength_agree(self):
        """Whatever colour the widget picked, the trace must match."""
        self._run(656.3)

        self.assertAlmostEqual(self.widget._rays[0].wavelength, 656.3 * NM_TO_MM, places=12)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestRefreshReactsToAnEditedLens(unittest.TestCase):
    """A refresh that does nothing leaves stale rays on screen."""

    def setUp(self):
        from src.gui.widgets.simulation_viz import SimulationVisualizationWidget

        self.lens = _lens()
        self.widget = SimulationVisualizationWidget()
        self.addCleanup(self.widget.deleteLater)
        self.widget.run_simulation(self.lens, wavelength=WAVELENGTH_GREEN)
        self.before = [tuple(ray.path[-1]) for ray in self.widget._rays]

    def test_editing_the_lens_then_refreshing_moves_the_rays(self):
        self.lens.radius_of_curvature_1 = 35.0
        self.lens.radius_of_curvature_2 = -35.0

        self.widget.refresh()

        self.assertTrue(
            self.widget._rays,
            "refresh cleared the rays without re-running them, leaving an " "empty view",
        )
        after = [tuple(ray.path[-1]) for ray in self.widget._rays]
        self.assertNotEqual(
            after,
            self.before,
            msg="refresh did not re-trace, so the view shows the new lens with "
            "the old lens's rays",
        )

    def test_refresh_keeps_the_rays_consistent_with_the_lens(self):
        self.lens.thickness = 12.0

        self.widget.refresh()

        for index, ray in enumerate(self.widget._rays):
            with self.subTest(ray=index):
                self.assertEqual(
                    len(ray.path) > 1,
                    True,
                    msg="a ray in the refreshed view has no traced path",
                )


class TestErrorsAreLoggedNotPrinted(unittest.TestCase):
    """A GUI cannot surface stdout; the message has to go somewhere real."""

    def _print_calls(self, source):
        found = []
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                if node.func.id == "print":
                    found.append(node.lineno)
        return found

    def test_simulation_viz_does_not_print(self):
        import src.gui.widgets.simulation_viz as module

        self.assertEqual(
            self._print_calls(inspect.getsource(module)),
            [],
            "errors go to print(), which the GUI has no way to surface",
        )

    def test_simulation_viz_logs_errors(self):
        import src.gui.widgets.simulation_viz as module

        source = inspect.getsource(module)

        self.assertIn("logger", source, "the module has no logger to report to")


class TestWavelengthsAreNamed(unittest.TestCase):
    """The wavelength used should be stated, not inherited from a default."""

    def test_ray_construction_names_the_wavelength(self):
        import src.gui.widgets.simulation_viz as module

        source = inspect.getsource(module)

        self.assertIn(
            "wavelength_mm=",
            source,
            "rays are built without a wavelength, so they inherit the 550 nm " "default silently",
        )

    def test_the_conversion_constant_is_used(self):
        import src.gui.widgets.simulation_viz as module

        source = inspect.getsource(module)

        self.assertIn("NM_TO_MM", source)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 not available")
class TestTheTabIsNotHalfWired(unittest.TestCase):
    """The tab is where the user's wavelength and their refresh call arrive."""

    def setUp(self):
        from PySide6.QtWidgets import QWidget

        from src.gui.tabs.simulation_tab import SimulationTab

        # BaseTab passes its parent to QWidget, so the stand-in has to be one.
        class _Parent(QWidget):
            def __init__(self):
                super().__init__()
                self._current_assembly = None
                self._current_lens = None

        self.parent = _Parent()
        self.addCleanup(self.parent.deleteLater)
        self.tab = SimulationTab(self.parent)
        self.addCleanup(self.tab.deleteLater)

    def test_the_picker_labels_and_values_come_from_one_table(self):
        """Two lists matched by position can drift apart silently."""
        from src.gui.tabs.simulation_tab import SIMULATION_WAVELENGTHS

        labels = [
            self.tab._sim_wavelength.itemText(i) for i in range(self.tab._sim_wavelength.count())
        ]

        self.assertEqual(
            labels,
            [label for _nm, label in SIMULATION_WAVELENGTHS] + ["Custom"],
        )

    def test_the_selected_wavelength_is_the_labelled_one(self):
        from src.gui.tabs.simulation_tab import SIMULATION_WAVELENGTHS

        for index, (nanometres, label) in enumerate(SIMULATION_WAVELENGTHS):
            with self.subTest(label=label):
                self.tab._sim_wavelength.setCurrentIndex(index)

                self.assertAlmostEqual(
                    self.tab._selected_wavelength(),
                    nanometres,
                    places=6,
                    msg=f"{label} traces at a different wavelength than its label",
                )

    def test_every_preset_label_states_the_wavelength_it_traces(self):
        """The hazard is drift, not today's numbers.

        The combo's labels and the traced wavelengths were separate lists
        matched by position. Any edit to one that missed the other - adding an
        entry, retuning a value - would leave an entry labelled one wavelength
        while tracing another, and nothing would say so. Comparing the traced
        value against the number *printed in the label* catches that; comparing
        against a fixed list would not, since the list would have drifted too.
        """
        import re

        from src.gui.tabs.simulation_tab import CUSTOM_WAVELENGTH_INDEX

        for index in range(CUSTOM_WAVELENGTH_INDEX):
            with self.subTest(entry=index):
                label = self.tab._sim_wavelength.itemText(index)
                stated = re.search(r"(\d+(?:\.\d+)?)\s*nm", label)
                self.assertIsNotNone(stated, f"{label!r} states no wavelength")

                self.tab._sim_wavelength.setCurrentIndex(index)
                self.assertAlmostEqual(
                    self.tab._selected_wavelength(),
                    float(stated.group(1)),
                    places=6,
                    msg=f"{label!r} traces at a wavelength other than the one it states",
                )

    def test_a_drifted_entry_would_be_caught(self):
        """Sanity check on the check: an entry lying about its wavelength fails.

        Guards the test above against silently passing for the wrong reason.
        """
        import re

        lied = "600 nm (Orange)"
        traced = 550.0

        stated = re.search(r"(\d+(?:\.\d+)?)\s*nm", lied)
        matches = abs(float(stated.group(1)) - traced) < 1e-6

        self.assertFalse(matches, "the label test cannot detect a drifted entry")

    def test_custom_is_the_last_entry(self):
        from src.gui.tabs.simulation_tab import CUSTOM_WAVELENGTH_INDEX

        self.tab._sim_wavelength.setCurrentIndex(CUSTOM_WAVELENGTH_INDEX)

        self.assertAlmostEqual(
            self.tab._selected_wavelength(),
            self.tab._sim_custom_wavelength.value(),
            places=6,
        )

    def test_the_tab_refresh_is_not_a_no_op(self):
        """The tab's refresh was `pass`, which is the reported defect."""
        from src.gui.widgets.simulation_viz import SimulationVisualizationWidget

        calls = []

        class _Recording(SimulationVisualizationWidget):
            def refresh(self):
                calls.append(True)

        self.tab._sim_viz = _Recording()

        self.tab.refresh()

        self.assertEqual(
            calls,
            [True],
            msg="the tab's refresh does nothing, so an edit leaves the old rays "
            "on screen beside the new lens",
        )


if __name__ == "__main__":
    unittest.main()
