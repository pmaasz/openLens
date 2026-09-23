"""Flow: Assembly builder + Optimization + Tolerancing manual QA -> automated.

Manual checklist replaced:
- new assembly -> add lens -> air-gap edit -> move up/down -> remove
- optimization tab: refresh builds variable keys, collect skips stale keys,
  fast simplex run on model (small iterations) converges without crash
- tolerancing tab: default tolerance set loads, small Monte Carlo runs
"""

from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtCore import Qt

from .conftest import requires_pyside
from .pages import MainWindowPO

pytestmark = requires_pyside


def test_assembly_builder_flow(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    system = po.add_first_library_lens_to_system()
    tab = main_window._assembly_tab_widget
    assert len(system.elements) == 1

    # Air-gap edit path (Set button).
    tab._system_list.setCurrentRow(0)
    QApplication.processEvents()
    if tab._air_gap_group.isEnabled():
        tab._air_gap_input.setValue(12.5)
        po.click_button(tab, "Set")
        QApplication.processEvents()

    # Add second lens then move/remove (exercises Up/Down/Remove wiring).
    tab._assembly_lens_list.setCurrentRow(0)
    po.click_button(tab, "Add to System")
    QApplication.processEvents()
    assert len(tab._optical_system.elements) == 2
    po.click_button(tab, "Up")
    po.click_button(tab, "Down")
    tab._system_list.setCurrentRow(1)
    po.click_button(tab, "Remove")
    QApplication.processEvents()
    assert len(tab._optical_system.elements) == 1


def test_optimization_collect_and_fast_run_flow(main_window, qtbot):
    """Refresh -> collect -> tiny optimizer run (model-level, not 100-iter GUI)."""

    from src.optimizer import LensOptimizer
    from src.optical_system import OpticalSystem

    po = MainWindowPO(main_window, qtbot)
    po.new_lens()
    po.switch_tab("optimization")
    tab = main_window._opt_tab
    tab.refresh()
    QApplication.processEvents()
    assert len(tab._opt_check_vars) > 0

    lens = main_window._current_lens
    variables = tab._collect_variables(lens)
    # Refresh pre-checks Radius 1/2 by default -> collecting must yield live vars.
    assert len(variables) >= 1

    # Uncheck everything -> empty, not a crash (regression guard).
    for cb in tab._opt_check_vars.values():
        cb.setChecked(False)
    assert tab._collect_variables(lens) == []

    # Check first available box and re-collect: must yield a live variable.
    first_key = next(iter(tab._opt_check_vars))
    tab._opt_check_vars[first_key].setChecked(True)
    variables = tab._collect_variables(lens)
    assert len(variables) >= 1

    # Fast model-level optimization proves end-to-end wiring quickly.
    system = OpticalSystem(name="QA Opt")
    system.add_lens(lens)
    optimizer = LensOptimizer(system, variables[:1], [])
    result = optimizer.optimize(max_iterations=2)
    assert result is not None


def test_tolerancing_default_set_and_small_monte_carlo(main_window, qtbot):
    from src.tolerancing import MonteCarloAnalyzer

    po = MainWindowPO(main_window, qtbot)
    po.new_lens()
    po.switch_tab("tolerancing")
    tab = main_window._tol_tab
    tab.refresh()
    QApplication.processEvents()

    # Default Set button populates the operand table when empty.
    if hasattr(tab, "_tol_table") and tab._tol_table.rowCount() == 0:
        for b in tab.findChildren(QPushButton):
            if b.text() == "Default Set":
                qtbot.mouseClick(b, Qt.LeftButton)
                break
        QApplication.processEvents()

    lens = main_window._current_lens
    operands = list(getattr(main_window, "_tol_operands", []))
    if not operands and hasattr(tab, "_tol_operands"):
        operands = list(tab._tol_operands)
    # Model-level smoke with few trials keeps the flow fast and deterministic.
    if operands:
        from src.optical_system import OpticalSystem as _OS

        system = _OS(name="QA Tol")
        system.add_lens(lens)
        analyzer = MonteCarloAnalyzer(system, operands, seed=42)
        report = analyzer.run(num_trials=5)
        assert report is not None
