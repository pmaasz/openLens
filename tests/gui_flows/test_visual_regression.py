"""Visual regression: every key view renders, no blank/crash, no major drift.

Covers the manual "eyeball every tab" checklist:
- lens editor 2D viz (biconvex + previously-NaN plano/inf geometry)
- simulation viz with traced rays
- assembly viz with a 2-element system
- full main window per tab (lens editor, simulation, performance)

First run bootstraps baselines under tests/gui_flows/__snapshots__/.
Later runs fail only on significant drift (see snapshots.py thresholds).
"""

from PySide6.QtWidgets import QApplication

from src.lens import Lens
from src.optical_system import OpticalSystem
from .conftest import requires_pyside
from .snapshots import assert_snapshot

pytestmark = requires_pyside


def _battery():
    return [
        Lens(
            radius_of_curvature_1=100.0, radius_of_curvature_2=-100.0, thickness=5.0, diameter=40.0
        ),
        Lens(
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=float("inf"),
            thickness=5.0,
            diameter=40.0,
        ),
    ]


def test_viz_widgets_render_and_match(main_window, qtbot):
    from src.gui.widgets.lens_viz_2d import LensViz2DWidget
    from src.gui.widgets.simulation_viz import SimulationVisualizationWidget
    from src.gui.widgets.assembly_viz import AssemblyVisualizationWidget

    lens = _battery()[0]

    w1 = LensViz2DWidget()
    qtbot.addWidget(w1)
    w1.update_lens(lens)
    assert_snapshot(w1, "lens_viz_2d_biconvex")

    w2 = SimulationVisualizationWidget()
    qtbot.addWidget(w2)
    w2.run_simulation(lens, num_rays=5)
    assert_snapshot(w2, "simulation_viz_singlet")

    system = OpticalSystem(name="QA Visual System")
    for L in _battery():
        system.add_lens(L, air_gap_before=5.0)
    w3 = AssemblyVisualizationWidget()
    qtbot.addWidget(w3)
    w3.update_system(system)
    assert_snapshot(w3, "assembly_viz_doublet")
    for w in (w1, w2, w3):
        w.close()


def test_main_window_tabs_render(main_window, qtbot):
    from .pages import MainWindowPO

    po = MainWindowPO(main_window, qtbot)
    po.new_lens()
    po.run_simulation(num_rays=5)
    for tab_name, shot in (
        ("lens_editor", "main_lens_editor"),
        ("simulation", "main_simulation"),
        ("performance", "main_performance"),
    ):
        po.switch_tab(tab_name)
        QApplication.processEvents()
        assert_snapshot(main_window, shot, width=1000, height=700)
