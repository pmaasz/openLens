#!/usr/bin/env python3
"""The lens editor properties panel is assembled from one builder per group (#564).

`_create_properties_panel` used to be 267 lines that built every group box in
one scope. The extraction is behaviour-preserving: the same inputs, in the same
groups and the same order. These tests pin that structure so a later edit cannot
silently drop a group from the panel.
"""

import os
import sys
import unittest
from unittest import mock

# Headless environments (CI): fall back to Qt's offscreen platform before
# any QApplication is created. A real DISPLAY always wins.
if os.environ.get("DISPLAY", "") == "" and sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtWidgets import QApplication, QGroupBox, QScrollArea

    from openlens.gui.widgets.lens_editor import LensEditorWidget
    from openlens.lens import Lens

    PYSIDE_AVAILABLE = True
except ImportError:  # pragma: no cover - depends on install
    QApplication = QGroupBox = QScrollArea = None  # type: ignore
    LensEditorWidget = Lens = None  # type: ignore
    PYSIDE_AVAILABLE = False


def _ensure_app():
    """Create (once) and return the QApplication every widget needs."""
    from tests import ensure_qapp

    return ensure_qapp()


#: Builders in panel order, and the title each group box must carry.
BUILDERS = (
    ("_create_name_group", "Name"),
    ("_create_classification_group", "Classification"),
    ("_create_dimensions_group", "Dimensions"),
    ("_create_mount_group", "Mount"),
    ("_create_parabolic_group", "Parabolic Surfaces (sag at D/2)"),
    ("_create_conic_group", "Conic Surfaces (K)"),
    ("_create_edge_profile_group", "Custom Edge Profile"),
    ("_create_material_group", "Material"),
    ("_create_coatings_group", "Coatings"),
    ("_create_fresnel_group", "Fresnel Lens"),
    ("_create_calculated_group", "Calculated Properties"),
)

#: Widget attributes the rest of the editor (and its tests) rely on.
NAMED_INPUTS = (
    "_name_input",
    "_class_type_label",
    "_r1_input",
    "_r2_input",
    "_thickness_input",
    "_diameter_input",
    "_ca1_input",
    "_ca2_input",
    "_bevel1_input",
    "_bevel2_input",
    "_lock_edge_check",
    "_mount_combo",
    "_manage_mounts_btn",
    "_para1_check",
    "_para1_sag_input",
    "_para2_check",
    "_para2_sag_input",
    "_conic1_input",
    "_conic2_input",
    "_edge_check",
    "_edge_points_input",
    "_material_combo",
    "_n_input",
    "_coat_combos",
    "_coat_wl_inputs",
    "_coat_info_labels",
    "_fresnel_check",
    "_groove_pitch_label",
    "_groove_pitch_input",
    "_num_grooves_label",
    "_num_grooves_value",
    "_focal_label",
    "_power_label",
    "_bfl_label",
    "_ffl_label",
    "_edge_label",
    "_feas_warning_label",
    "_working_flange_label",
)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class TestPropertiesPanelStructure(unittest.TestCase):
    """The panel is a thin assembly of per-group builders."""

    def setUp(self):
        _ensure_app()
        self.editor = LensEditorWidget()

    def tearDown(self):
        self.editor.close()
        self.editor.deleteLater()
        QApplication.processEvents()

    def test_every_group_has_a_builder(self):
        for name, _title in BUILDERS:
            with self.subTest(builder=name):
                self.assertTrue(callable(getattr(self.editor, name, None)))

    def test_panel_calls_the_builders_in_order(self):
        calls = []

        def make_builder(name):
            def builder(_self):
                calls.append(name)
                return QGroupBox(name)

            return builder

        patches = {name: make_builder(name) for name, _title in BUILDERS}
        with mock.patch.multiple(LensEditorWidget, **patches):
            frame = self.editor._create_properties_panel()

        self.assertEqual(calls, [name for name, _title in BUILDERS])
        self.assertEqual(frame.layout().count(), len(BUILDERS) + 1)  # + stretch

    def test_group_titles_keep_their_order(self):
        scroll = self.editor.findChild(QScrollArea)
        self.assertIsNotNone(scroll)
        layout = scroll.widget().layout()

        titles = [
            layout.itemAt(index).widget().title()
            for index in range(layout.count())
            if layout.itemAt(index).widget() is not None
        ]
        self.assertEqual(titles, [title for _name, title in BUILDERS])

    def test_every_named_input_survives_the_extraction(self):
        for name in NAMED_INPUTS:
            with self.subTest(attribute=name):
                self.assertTrue(hasattr(self.editor, name), name)

        self.assertEqual(len(self.editor._coat_combos), 2)
        self.assertEqual(len(self.editor._coat_wl_inputs), 2)
        self.assertEqual(len(self.editor._coat_info_labels), 2)

    def test_name_input_is_still_wired_to_the_model(self):
        lens = Lens(name="Before")
        self.editor.load_lens(lens)

        self.editor._name_input.setText("After")

        self.assertEqual(lens.name, "After")


if __name__ == "__main__":
    unittest.main()
