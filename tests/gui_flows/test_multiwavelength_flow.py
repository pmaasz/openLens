"""Flow: trace several wavelengths, and white light, from the simulation tab (#72)."""

from PySide6.QtWidgets import QApplication

from openlens.constants import NM_TO_MM, WAVELENGTH_GREEN, WAVELENGTH_RED
from openlens.gui.tabs.simulation_tab import (
    SIMULATION_WAVELENGTHS,
    WHITE_LIGHT_WAVELENGTHS,
)

from .conftest import requires_pyside
from .pages import MainWindowPO

pytestmark = requires_pyside


def _add_preset(po, tab, wavelength):
    index = next(
        index
        for index, (nanometres, _label) in enumerate(SIMULATION_WAVELENGTHS)
        if abs(nanometres - wavelength) < 1e-9
    )
    tab._sim_wavelength.setCurrentIndex(index)
    po.click_button(tab, "Add")
    QApplication.processEvents()


def test_run_traces_every_wavelength_in_the_list(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    po.new_lens()
    po.switch_tab("simulation")
    tab = main_window._sim_tab

    _add_preset(po, tab, WAVELENGTH_RED)
    po.click_button(tab, "Run Simulation")

    assert tab._selected_wavelengths() == [WAVELENGTH_GREEN, WAVELENGTH_RED]
    groups = tab._sim_viz._ray_groups
    assert len(groups) == 2
    traced = [group[0].wavelength / NM_TO_MM for _colour, group in groups]
    assert traced == [WAVELENGTH_GREEN, WAVELENGTH_RED]
    for _colour, group in groups:
        assert group, "a selected wavelength traced no rays"


def test_white_light_switch_traces_the_visible_spectrum(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    po.new_lens()
    po.switch_tab("simulation")
    tab = main_window._sim_tab

    tab._sim_white_light.setChecked(True)
    po.click_button(tab, "Run Simulation")

    selected = tab._selected_wavelengths()
    assert selected == list(WHITE_LIGHT_WAVELENGTHS)
    assert len(tab._sim_viz._ray_groups) == len(WHITE_LIGHT_WAVELENGTHS)
    assert not tab._sim_wavelengths.isEnabled()
