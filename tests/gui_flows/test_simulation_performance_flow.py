"""Flow: Simulation + Performance manual QA -> automated.

Manual checklist replaced:
- Simulation tab: set rays/angle, Run, rays appear, Clear, Reset View,
  ghost checkbox path
- Performance tab: Calculate Metrics populates dashboard (no placeholder)
- PSF/MTF/Wavefront/Ghost analysis entry points do not crash on a singlet
"""

from PySide6.QtWidgets import QApplication

from .conftest import requires_pyside
from .pages import MainWindowPO

pytestmark = requires_pyside


def test_simulation_run_clear_reset_flow(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    rays = po.run_simulation(num_rays=7)
    assert len(rays) == 7

    tab = main_window._sim_tab
    po.clear_simulation()
    assert len(tab._sim_viz._rays) == 0

    # Run again + reset view (zoom/pan state must not crash).
    po.run_simulation(num_rays=5, angle=5.0)
    tab._reset_simulation_view()
    QApplication.processEvents()
    assert len(tab._sim_viz._rays) == 5


def test_simulation_ghost_path(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    rays = po.run_simulation(num_rays=5, ghosts=True)
    assert len(rays) > 0


def test_performance_metrics_flow(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    text = po.calculate_performance()
    assert len(text) > 50


def test_analysis_dialogs_smoke(main_window, qtbot, monkeypatch):
    """PSF/MTF/Wavefront/Ghost slots build their dialogs without crashing.

    Dialogs are exec()'d in production; here we auto-accept them.
    """
    from src.gui.dialogs import AnalysisPlotDialog

    monkeypatch.setattr(AnalysisPlotDialog, "exec", lambda self: 0)
    po = MainWindowPO(main_window, qtbot)
    po.new_lens()
    QApplication.processEvents()
    # Each slot must not raise; failures surface as MessageBox + exception.
    main_window._on_show_psf()
    main_window._on_show_mtf()
    main_window._on_show_wavefront()
    main_window._on_show_ghost_analysis()
    QApplication.processEvents()
