"""Page-object helpers for OpenLens QA flows.

Wraps OpenLensWindow so flow tests read like the manual click-through
checklist: new lens -> edit -> simulate -> performance -> assembly ->
optimize -> tolerance -> save/export -> theme. Uses real widgets
(spinboxes, buttons, tabs) via qtbot where it adds value, and calls slots
directly where that is deterministic headless.
"""

from typing import Optional

from PySide6.QtWidgets import QApplication, QPushButton
from PySide6.QtTest import QTest
from PySide6.QtCore import Qt

TAB_INDEX = {
    "lens_editor": 0,
    "assembly": 1,
    "simulation": 2,
    "performance": 3,
    "optimization": 4,
    "tolerancing": 5,
}


class MainWindowPO:
    """Page object for OpenLensWindow."""

    def __init__(self, window, qtbot):
        self.w = window
        self.qtbot = qtbot

    # -- navigation --
    def switch_tab(self, name: str):
        idx = TAB_INDEX[name]
        self.w._editor_tabs.setCurrentIndex(idx)
        QApplication.processEvents()
        assert self.w._editor_tabs.currentIndex() == idx
        return self.current_tab()

    def current_tab(self):
        return self.w._editor_tabs.currentWidget()

    # -- lens library --
    def new_lens(self):
        n = len(self.w._lenses)
        self.w._on_new_lens()
        QApplication.processEvents()
        assert len(self.w._lenses) == n + 1
        return self.w._current_lens

    def new_assembly(self):
        n = len(self.w._assemblies)
        self.w._on_new_assembly()
        QApplication.processEvents()
        assert len(self.w._assemblies) == n + 1
        assert self.w._editor_tabs.isTabVisible(TAB_INDEX["assembly"])
        return self.w._current_assembly

    def duplicate_current_lens(self):
        assert self.w._current_lens is not None
        n = len(self.w._lenses)
        self.w._on_duplicate_lens()
        QApplication.processEvents()
        assert len(self.w._lenses) == n + 1
        return self.w._current_lens

    def edit_current_lens(
        self,
        r1: Optional[float] = None,
        r2: Optional[float] = None,
        thickness: Optional[float] = None,
        diameter: Optional[float] = None,
    ):
        ed = self.w._lens_editor
        if r1 is not None:
            ed._r1_input.setValue(r1)
        if r2 is not None:
            ed._r2_input.setValue(r2)
        if thickness is not None:
            ed._thickness_input.setValue(thickness)
        if diameter is not None:
            ed._diameter_input.setValue(diameter)
        QApplication.processEvents()
        return self.w._current_lens

    def click_button(self, parent, text: str):
        """Find a QPushButton by visible text under parent and left-click it."""
        btn = None
        # findChild by type alone is ambiguous; search manually by text.
        for b in parent.findChildren(QPushButton):
            if b.text() == text:
                btn = b
                break
        assert btn is not None, f"button '{text}' not found"
        QTest.mouseClick(btn, Qt.LeftButton)
        QApplication.processEvents()
        return btn

    # -- simulation flow (SimulationTab) --
    def run_simulation(self, num_rays: int = 7, angle: float = 0.0, ghosts: bool = False):
        self.switch_tab("simulation")
        tab = self.w._sim_tab
        tab._sim_num_rays.setValue(num_rays)
        tab._sim_angle.setValue(angle)
        tab._ghost_analysis.setChecked(ghosts)
        self.click_button(tab, "Run Simulation")
        QApplication.processEvents()
        assert len(tab._sim_viz._rays) > 0
        return tab._sim_viz._rays

    def clear_simulation(self):
        tab = self.w._sim_tab
        self.click_button(tab, "Clear")
        QApplication.processEvents()

    # -- performance flow (PerformanceTab) --
    def calculate_performance(self):
        self.switch_tab("performance")
        tab = self.w._perf_tab
        self.click_button(tab, "Calculate Metrics")
        QApplication.processEvents()
        text = tab._perf_metrics_text.toPlainText()
        assert "Select a lens" not in text
        return text

    # -- assembly flow (AssemblyTab) --
    def add_first_library_lens_to_system(self):
        self.new_assembly()
        self.switch_tab("assembly")
        tab = self.w._assembly_tab_widget
        tab.refresh()
        QApplication.processEvents()
        assert tab._assembly_lens_list.count() > 0
        tab._assembly_lens_list.setCurrentRow(0)
        self.click_button(tab, "Add to System")
        QApplication.processEvents()
        assert len(tab._optical_system.elements) >= 1
        return tab._optical_system

    # -- theme / view --
    def toggle_theme(self):
        before = self.w._theme
        self.w._on_toggle_theme()
        QApplication.processEvents()
        assert self.w._theme != before
        return self.w._theme
