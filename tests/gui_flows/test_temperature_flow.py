"""Flow: simulate a lens at a user-selected temperature (#10)."""

from openlens.constants import ABSOLUTE_ZERO_C, DEFAULT_TEMPERATURE

from .conftest import requires_pyside
from .pages import MainWindowPO

pytestmark = requires_pyside


def test_hot_run_conditions_a_copy_and_leaves_the_library_lens_alone(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    lens = po.new_lens()
    po.switch_tab("simulation")
    tab = main_window._sim_tab

    tab._sim_temperature.setValue(120.0)
    po.click_button(tab, "Run Simulation")

    traced = tab._sim_viz._lens
    assert traced is not lens
    assert traced.temperature == 120.0
    assert traced.radius_of_curvature_1 > lens.radius_of_curvature_1
    assert lens.temperature == DEFAULT_TEMPERATURE
    assert tab._sim_viz._rays


def test_the_control_cannot_go_below_zero_kelvin_and_still_traces(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    po.new_lens()
    po.switch_tab("simulation")
    tab = main_window._sim_tab

    tab._sim_temperature.setValue(-400.0)

    assert tab._sim_temperature.value() == ABSOLUTE_ZERO_C
    po.click_button(tab, "Run Simulation")
    assert tab._sim_viz._lens.temperature == ABSOLUTE_ZERO_C
    assert tab._sim_viz._rays
