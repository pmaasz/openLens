"""#668: "Clear" must keep an assembly's simulation cleared until Run is pressed."""

import os
import sys
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QWidget

    PYSIDE_AVAILABLE = True
    _PYSIDE_ERROR = ""
except ImportError as _e:  # pragma: no cover - environment guard
    PYSIDE_AVAILABLE = False
    _PYSIDE_ERROR = str(_e)

if PYSIDE_AVAILABLE:
    app = QApplication.instance() or QApplication(sys.argv)


@unittest.skipUnless(PYSIDE_AVAILABLE, f"PySide6 not available: {_PYSIDE_ERROR}")
class TestClearSimulationSticks(unittest.TestCase):
    class _FakeWindow(QWidget):
        def __init__(self, target):
            super().__init__()
            self._target = target

        def _active_target(self):
            return self._target

    def _assembly(self):
        from openlens.lens import Lens
        from openlens.optical_system import OpticalSystem

        system = OpticalSystem(name="Doublet")
        system.add_lens(
            Lens(
                name="L1",
                radius_of_curvature_1=50.0,
                radius_of_curvature_2=-50.0,
                refractive_index=1.5168,
                thickness=5.0,
                diameter=25.0,
            )
        )
        system.add_lens(
            Lens(
                name="L2",
                radius_of_curvature_1=-60.0,
                radius_of_curvature_2=60.0,
                refractive_index=1.62,
                thickness=4.0,
                diameter=25.0,
            ),
            air_gap_before=2.0,
        )
        return system

    def _lens(self):
        from openlens.lens import Lens

        return Lens(
            name="Single",
            radius_of_curvature_1=50.0,
            radius_of_curvature_2=-50.0,
            refractive_index=1.5168,
            thickness=5.0,
            diameter=25.0,
        )

    def _tab(self, target):
        from openlens.gui.tabs.simulation_tab import SimulationTab

        tab = SimulationTab(self._FakeWindow(target))
        tab.resize(900, 600)
        tab._on_run_simulation()
        self.assertGreater(len(tab._sim_viz._rays), 0)
        return tab

    def test_an_assembly_stays_cleared_after_a_refresh(self):
        system = self._assembly()
        tab = self._tab(system)
        viz = tab._sim_viz

        tab._on_clear_simulation()
        self.assertEqual(len(viz._rays), 0)
        self.assertIsNone(viz._system)

        # Any edit in the editor refreshes every tab.
        system.elements[0].lens.radius_of_curvature_1 = 75.0
        tab.refresh()

        self.assertEqual(len(viz._rays), 0)
        self.assertIsNone(viz._system)

    def test_a_single_lens_stays_cleared_after_a_refresh(self):
        lens = self._lens()
        tab = self._tab(lens)
        viz = tab._sim_viz

        tab._on_clear_simulation()
        self.assertEqual(len(viz._rays), 0)
        self.assertIsNone(viz._lens)

        lens.radius_of_curvature_1 = 75.0
        tab.refresh()

        self.assertEqual(len(viz._rays), 0)
        self.assertIsNone(viz._lens)

    def test_run_after_clear_restores_the_rays(self):
        system = self._assembly()
        tab = self._tab(system)
        viz = tab._sim_viz

        tab._on_clear_simulation()
        tab._on_run_simulation()

        self.assertIsNotNone(viz._system)
        self.assertGreater(len(viz._rays), 0)


if __name__ == "__main__":
    unittest.main()
