"""Flow: simulate a lens at a user-selected temperature (#10)."""

from openlens.constants import ABSOLUTE_ZERO_C, DEFAULT_TEMPERATURE

from .conftest import requires_pyside
from .pages import MainWindowPO

pytestmark = requires_pyside


def test_hot_run_conditions_a_copy_and_leaves_the_library_lens_alone(main_window, qtbot):
    """The trace must use a conditioned copy, and the stored lens must be alone.

    The widget keeps the live model - so an edit of the lens is picked up by
    the next trace - and the environment is applied at trace time, through the
    conditioner.
    """
    po = MainWindowPO(main_window, qtbot)
    lens = po.new_lens()
    po.switch_tab("simulation")
    tab = main_window._sim_tab

    tab._sim_temperature.setValue(120.0)
    po.click_button(tab, "Run Simulation")

    # The widget holds the live model.
    assert tab._sim_viz._lens is lens
    assert lens.temperature == DEFAULT_TEMPERATURE

    # The trace uses a conditioned copy of it.
    conditioned = tab._sim_viz._conditioner(lens)
    assert conditioned is not lens
    assert conditioned.temperature == 120.0
    assert conditioned.radius_of_curvature_1 > lens.radius_of_curvature_1
    assert tab._sim_viz._rays


def test_the_control_cannot_go_below_zero_kelvin_and_still_traces(main_window, qtbot):
    po = MainWindowPO(main_window, qtbot)
    lens = po.new_lens()
    po.switch_tab("simulation")
    tab = main_window._sim_tab

    tab._sim_temperature.setValue(-400.0)

    assert tab._sim_temperature.value() == ABSOLUTE_ZERO_C
    po.click_button(tab, "Run Simulation")
    assert tab._sim_viz._conditioner(lens).temperature == ABSOLUTE_ZERO_C
    assert tab._sim_viz._rays
