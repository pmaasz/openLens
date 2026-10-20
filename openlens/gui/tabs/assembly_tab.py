"""
OpenLens PySide6 Assembly Tab
Multi-element optical system builder
"""

import copy
import functools
import logging
from datetime import datetime
from typing import Optional

from PySide6.QtGui import QUndoCommand, QUndoStack
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QFormLayout,
    QComboBox,
    QDoubleSpinBox,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QFrame,
    QSizePolicy,
)
from .base_tab import BaseTab
from ..widgets.assembly_viz import AssemblyVisualizationWidget
from ...optical_system import OpticalSystem, AirGap

logger = logging.getLogger(__name__)


class _AssemblySnapshotCommand(QUndoCommand):
    """Restore a whole ``OpticalSystem`` to a snapshot on undo/redo.

    Assembly edits reach into the flat element list, the node tree, air gaps,
    aperture stop and metadata.  A snapshot command keeps every operation -
    add, remove, reorder, gap, alignment and stop - exact without a command
    class per property.
    """

    def __init__(self, tab, system, before, after, label) -> None:
        super().__init__(label)
        self._tab = tab
        self._system = system
        self._before = before
        self._after = after
        # QUndoStack.push() calls redo() once.  The edit handler has already
        # applied the change, so that first callback must not restore it again.
        self._first_redo = True

    def undo(self) -> None:
        """Restore the state captured before the edit."""
        self._restore(self._before)

    def redo(self) -> None:
        """Reapply the state captured after the edit."""
        if self._first_redo:
            self._first_redo = False
            return
        self._restore(self._after)

    def _restore(self, snapshot) -> None:
        tab = self._tab
        if tab._optical_system is not self._system:
            # The editor moved on; a stale command must not mutate another
            # system.  Loading a different system clears the stack anyway.
            return

        tab._restoring = True
        try:
            current = self._system.__dict__
            current.clear()
            current.update(copy.deepcopy(snapshot))
            self._system.modified_at = datetime.now().isoformat()
            tab._refresh_assembly_ui()
            tab._on_assembly_changed()
        finally:
            tab._restoring = False


def _undoable_assembly_edit(label: str):
    """Record one whole-system undo command around a user-edit handler.

    Nested handlers are folded into the outermost command, like the lens
    editor's ``_undoable_edit``.  A handler that makes no model change does not
    grow the history.
    """

    def decorator(method):
        accepted = method.__code__.co_argcount - 1

        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            # Qt signals may pass an argument the handler does not use (for
            # example clicked(bool)); trim it before forwarding.
            args = args[:accepted]
            if self._optical_system is None or self._restoring or self._edit_depth:
                return method(self, *args, **kwargs)

            before_state = self._optical_system.to_dict()
            before = copy.deepcopy(self._optical_system.__dict__)
            self._edit_depth += 1
            try:
                result = method(self, *args, **kwargs)
                after_state = self._optical_system.to_dict()
            finally:
                self._edit_depth -= 1

            if after_state != before_state:
                after = copy.deepcopy(self._optical_system.__dict__)
                self._undo_stack.push(
                    _AssemblySnapshotCommand(self, self._optical_system, before, after, label)
                )
            return result

        return wrapper

    return decorator


class AssemblyTab(BaseTab):
    """Multi-element optical system builder"""

    #: Retry budget for an empty lens list, and the delay between attempts.
    #: The database load is asynchronous, so a short wait is legitimate - but
    #: it must be bounded. See refresh_lens_list.
    LENS_LIST_RETRY_MS = 100
    LENS_LIST_MAX_RETRIES = 20

    @property
    def undo_stack(self) -> QUndoStack:
        """The assembly editor's undo history (one command per edit)."""
        return self._undo_stack

    def _setup_ui(self) -> None:
        """Build the builder panels and create the initial optical system."""
        self._undo_stack = QUndoStack(self)
        self._restoring = False
        self._edit_depth = 0
        layout = QHBoxLayout(self)

        # Left: Available lenses + System builder. Minimum width keeps
        # the editors readable when the visualization pane expands; the
        # scroll area keeps every group reachable on short windows.
        left_panel = QWidget()
        left_panel.setMinimumWidth(300)
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_scroll.setWidget(left_panel)
        left_scroll.setMinimumWidth(320)
        left_layout = QVBoxLayout(left_panel)

        # Lens selection
        lens_sel_group = QGroupBox("Lens Selection")
        lens_sel_layout = QVBoxLayout(lens_sel_group)
        self._assembly_lens_list = QListWidget()
        self._assembly_lens_list.setMinimumHeight(90)
        lens_sel_layout.addWidget(self._assembly_lens_list)

        add_btn = QPushButton("Add to System")
        add_btn.clicked.connect(self._on_add_lens_to_system)
        lens_sel_layout.addWidget(add_btn)

        left_layout.addWidget(lens_sel_group)

        # System builder
        sys_group = QGroupBox("System Builder")
        sys_layout = QVBoxLayout(sys_group)
        self._system_list = QListWidget()
        self._system_list.setMinimumHeight(90)
        self._system_list.currentRowChanged.connect(self._on_system_item_selected)
        sys_layout.addWidget(self._system_list)

        # Air Gap Editor (contextual)
        self._air_gap_group = QGroupBox("Air Gap (Before Selected Element)")
        self._air_gap_group.setEnabled(False)
        ag_layout = QFormLayout(self._air_gap_group)
        ag_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        input_row = QHBoxLayout()
        self._air_gap_input = QDoubleSpinBox()
        self._air_gap_input.setRange(0, 1000)
        self._air_gap_input.setDecimals(3)
        self._air_gap_input.setSingleStep(0.1)
        self._air_gap_input.setSuffix(" mm")
        self._air_gap_input.setMinimumWidth(110)
        # Removed the direct valueChanged connection to prevent jumping during typing

        self._apply_gap_btn = QPushButton("Set")
        self._apply_gap_btn.setFixedWidth(60)
        self._apply_gap_btn.clicked.connect(self._on_apply_gap_clicked)

        input_row.addWidget(self._air_gap_input)
        input_row.addWidget(self._apply_gap_btn)

        ag_layout.addRow("Thickness:", input_row)
        sys_layout.addWidget(self._air_gap_group)

        btn_row = QHBoxLayout()
        up_btn = QPushButton("Up")
        up_btn.clicked.connect(self._on_move_lens_up)
        down_btn = QPushButton("Down")
        down_btn.clicked.connect(self._on_move_lens_down)
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._on_remove_lens_from_system)
        btn_row.addWidget(up_btn)
        btn_row.addWidget(down_btn)
        btn_row.addWidget(remove_btn)
        sys_layout.addLayout(btn_row)

        left_layout.addWidget(sys_group)

        # Aperture stop: which air gap holds the stop, and its diameter.
        # 0 diameter = unspecified (position only).
        stop_group = QGroupBox("Aperture Stop")
        stop_layout = QFormLayout(stop_group)
        stop_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self._stop_gap_combo = QComboBox()
        self._stop_gap_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._stop_gap_combo.setMinimumWidth(140)
        stop_layout.addRow("Gap:", self._stop_gap_combo)
        self._stop_dia_input = QDoubleSpinBox()
        self._stop_dia_input.setRange(0, 500)
        self._stop_dia_input.setDecimals(3)
        self._stop_dia_input.setSingleStep(0.1)
        self._stop_dia_input.setSuffix(" mm")
        self._stop_dia_input.setMinimumWidth(110)
        stop_layout.addRow("Diameter (0 = n/a):", self._stop_dia_input)
        stop_btn_row = QHBoxLayout()
        stop_set_btn = QPushButton("Set")
        stop_set_btn.clicked.connect(self._on_stop_set_clicked)
        stop_clear_btn = QPushButton("Clear")
        stop_clear_btn.clicked.connect(self._on_stop_clear_clicked)
        stop_btn_row.addWidget(stop_set_btn)
        stop_btn_row.addWidget(stop_clear_btn)
        stop_layout.addRow(stop_btn_row)
        left_layout.addWidget(stop_group)

        # Element alignment: decenter/tilt of the selected element.
        self._align_group = QGroupBox("Element Alignment")
        self._align_group.setEnabled(False)
        align_layout = QFormLayout(self._align_group)
        align_layout.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        self._decenter_y_input = QDoubleSpinBox()
        self._decenter_y_input.setRange(-10, 10)
        self._decenter_y_input.setDecimals(3)
        self._decenter_y_input.setSuffix(" mm")
        self._decenter_y_input.setMinimumWidth(110)
        align_layout.addRow("Decenter Y:", self._decenter_y_input)
        self._decenter_z_input = QDoubleSpinBox()
        self._decenter_z_input.setRange(-10, 10)
        self._decenter_z_input.setDecimals(3)
        self._decenter_z_input.setSuffix(" mm")
        self._decenter_z_input.setMinimumWidth(110)
        align_layout.addRow("Decenter Z:", self._decenter_z_input)
        self._tilt_inputs = []
        for axis in ("X", "Y", "Z"):
            spin = QDoubleSpinBox()
            spin.setRange(-5, 5)
            spin.setDecimals(3)
            spin.setSuffix(" deg")
            spin.setMinimumWidth(110)
            align_layout.addRow(f"Tilt {axis}:", spin)
            self._tilt_inputs.append(spin)
        align_apply_btn = QPushButton("Apply to selected element")
        align_apply_btn.clicked.connect(self._on_align_apply_clicked)
        align_layout.addRow(align_apply_btn)
        left_layout.addWidget(self._align_group)

        layout.addWidget(left_scroll, 1)

        # Right: 2D visualization
        self._assembly_viz = AssemblyVisualizationWidget()
        layout.addWidget(self._assembly_viz, 2)

        # Create optical system
        self._optical_system = OpticalSystem(name="New Assembly")
        self.refresh_lens_list()

    def _cancel_lens_list_retry(self) -> None:
        """Stop any pending lens-list retry and reset the counter."""
        timer = getattr(self, "_lens_list_retry_timer", None)
        if timer is not None:
            timer.stop()
            self._lens_list_retry_timer = None
        self._lens_list_retries = 0

    def refresh_lens_list(self) -> None:
        """Populate the lens selection list from the main window's lens collection.

        The database load is asynchronous, so an empty list shortly after
        startup can just mean "not loaded yet" - hence a short retry. It used
        to be QTimer.singleShot(100, self.refresh_lens_list) with no cap, no
        cancellation and no give-up state, so a library that never fills
        (openlens.py sets _lenses = [] on the database-load failure path) woke
        the Qt event loop 10x/second for the whole session: measurable
        constant CPU, and it hid the real problem behind a permanently empty
        list.

        The retry is now bounded, the timer is held so it can be cancelled,
        and exhausting the budget shows a placeholder that names the likely
        cause instead of an unexplained empty list. The counter resets on
        success, so a later genuine reload is retried normally.
        """
        if not hasattr(self, "_lens_list_retries"):
            self._lens_list_retries = 0
            self._lens_list_retry_timer = None

        self._assembly_lens_list.clear()
        lenses = getattr(self._parent, "_lenses", None) or []
        for lens in lenses:
            self._assembly_lens_list.addItem(lens.name)

        if self._assembly_lens_list.count():
            self._cancel_lens_list_retry()
            return

        if self._lens_list_retries >= self.LENS_LIST_MAX_RETRIES:
            if self._lens_list_retry_timer is not None:
                self._lens_list_retry_timer.stop()
                self._lens_list_retry_timer = None
            if self._assembly_lens_list.count() == 0:
                item = QListWidgetItem("(no lenses loaded - check the lens database)")
                # A hint, not a selectable lens: drop selectability so a
                # double-click cannot try to add it to the system.
                selectable = QListWidgetItem.flags(item).ItemIsSelectable
                item.setFlags(item.flags() & ~selectable)
                self._assembly_lens_list.addItem(item)
                logger.warning(
                    "Lens list still empty after %d retries; showing a "
                    "placeholder rather than polling indefinitely",
                    self.LENS_LIST_MAX_RETRIES,
                )
            return

        self._lens_list_retries += 1
        from PySide6.QtCore import QTimer

        if self._lens_list_retry_timer is None:
            self._lens_list_retry_timer = QTimer(self)
            self._lens_list_retry_timer.setSingleShot(True)
            self._lens_list_retry_timer.timeout.connect(self.refresh_lens_list)
        self._lens_list_retry_timer.start(self.LENS_LIST_RETRY_MS)

    def _update_system_list(self) -> None:
        """Update the system list widget from the optical system model.

        Rebuilding the list used to drop the selection after every edit, which
        also disabled the contextual gap/alignment editors.  Keep the row where
        possible so undo/redo restores the same visible element.
        """
        row = self._system_list.currentRow()
        self._system_list.clear()
        stop = self._optical_system.get_aperture_stop()
        stop_gap = stop["gap_index"] if stop is not None else None
        for i, element in enumerate(self._optical_system.elements):
            # Air gap before element i is at index i-1
            gap_str = ""
            if i > 0 and i - 1 < len(self._optical_system.air_gaps):
                gap = self._optical_system.air_gaps[i - 1]
                gap_value = gap.thickness if isinstance(gap, AirGap) else gap
                gap_str = f" (Gap: {gap_value:.3f}mm)"
                if stop_gap is not None and i - 1 == stop_gap:
                    dia = stop.get("diameter")
                    gap_str += f" STOP{f' Ø{dia:.2f}mm' if dia else ''}"
            align_str = ""
            if any(
                abs(getattr(element, attr, 0.0) or 0.0) > 1e-12
                for attr in ("decenter_y", "decenter_z", "tilt_x", "tilt_y", "tilt_z")
            ):
                align_str = " [aligned≠0]"

            item = QListWidgetItem(f"{i+1}: {element.lens.name}{gap_str}{align_str}")
            self._system_list.addItem(item)
        self._refresh_stop_ui()
        if row >= 0 and self._system_list.count():
            self._system_list.setCurrentRow(min(row, self._system_list.count() - 1))

    def _refresh_assembly_ui(self) -> None:
        """Repaint the widget tree from the current optical system.

        Used after a programmatic load and after undo/redo.  The selected row is
        kept where possible so the contextual air-gap and alignment editors stay
        pointed at the same element.
        """
        if self._optical_system is None:
            self._system_list.clear()
            self._air_gap_group.setEnabled(False)
            self._align_group.setEnabled(False)
            combo = self._stop_gap_combo
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("(no air gaps)", -1)
            combo.setEnabled(False)
            combo.blockSignals(False)
            self._stop_dia_input.setValue(0.0)
            self._assembly_viz.update_system(None)
            return

        row = self._system_list.currentRow()
        self._update_system_list()
        count = len(self._optical_system.elements)
        if count:
            row = 0 if row < 0 else min(row, count - 1)
            self._system_list.setCurrentRow(row)
        else:
            self._system_list.setCurrentRow(-1)
            self._air_gap_group.setEnabled(False)
            self._align_group.setEnabled(False)
        self._assembly_viz.update_system(self._optical_system)

    def load_system(self, system: Optional[OpticalSystem]) -> None:
        """Bind the editor to *system* without recording an undo command.

        Loading a different system clears the previous history: its commands
        hold snapshots of another model and must never be replayed here.
        Refreshing the same system keeps the history intact.

        Args:
            system: The optical system to display, or None to clear the editor.
        """
        if system is self._optical_system:
            self._refresh_assembly_ui()
            return

        self._restoring = True
        try:
            self._optical_system = system
            self._undo_stack.clear()
            # The old row number means nothing in the new system.
            self._system_list.setCurrentRow(-1)
            self._refresh_assembly_ui()
        finally:
            self._restoring = False

    def _refresh_stop_ui(self) -> None:
        """Rebuild the stop gap combo and reflect the current stop."""
        combo = self._stop_gap_combo
        combo.blockSignals(True)
        combo.clear()
        gaps = self._optical_system.air_gaps
        if not gaps:
            combo.addItem("(no air gaps)", -1)
            combo.setEnabled(False)
        else:
            combo.setEnabled(True)
            for g in range(len(gaps)):
                combo.addItem(f"Gap {g} (before element {g + 2})", g)
        stop = self._optical_system.get_aperture_stop()
        if stop is not None:
            idx = combo.findData(stop["gap_index"])
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            dia = stop.get("diameter")
            self._stop_dia_input.setValue(dia if dia else 0.0)
        else:
            combo.setCurrentIndex(0)
            self._stop_dia_input.setValue(0.0)
        combo.blockSignals(False)

    @_undoable_assembly_edit("Set aperture stop")
    def _on_stop_set_clicked(self) -> None:
        """Place the aperture stop in the selected gap."""
        gap_index = self._stop_gap_combo.currentData()
        if gap_index is None or gap_index < 0:
            return
        diameter = self._stop_dia_input.value()
        try:
            self._optical_system.set_aperture_stop(
                int(gap_index), diameter if diameter > 0 else None
            )
        except ValueError:
            return
        self._update_system_list()
        self._assembly_viz.update_system(self._optical_system)
        self._on_assembly_changed()

    @_undoable_assembly_edit("Clear aperture stop")
    def _on_stop_clear_clicked(self) -> None:
        """Remove the aperture stop definition."""
        if self._optical_system.get_aperture_stop() is None:
            return
        self._optical_system.clear_aperture_stop()
        self._update_system_list()
        self._assembly_viz.update_system(self._optical_system)
        self._on_assembly_changed()

    @_undoable_assembly_edit("Edit element alignment")
    def _on_align_apply_clicked(self) -> None:
        """Apply decenter/tilt values to the selected element."""
        current = self._system_list.currentRow()
        if current < 0 or current >= len(self._optical_system.elements):
            return
        tilts = [spin.value() for spin in self._tilt_inputs]
        if self._optical_system.set_element_alignment(
            current,
            decenter_y=self._decenter_y_input.value(),
            decenter_z=self._decenter_z_input.value(),
            tilt_x=tilts[0],
            tilt_y=tilts[1],
            tilt_z=tilts[2],
        ):
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()

    @_undoable_assembly_edit("Add element")
    def _on_add_lens_to_system(self) -> None:
        """Add selected lens to optical system."""
        current = self._assembly_lens_list.currentRow()
        if current >= 0 and current < len(self._parent._lenses):
            lens = self._parent._lenses[current]
            # Default gap 5.0mm if not the first element
            gap = 5.0 if self._optical_system.elements else 0.0
            self._optical_system.add_lens(lens, air_gap_before=gap)
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()

    @_undoable_assembly_edit("Remove element")
    def _on_remove_lens_from_system(self) -> None:
        """Remove selected lens from system."""
        current = self._system_list.currentRow()
        if current >= 0 and current < len(self._optical_system.elements):
            self._optical_system.remove_lens(current)
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()

    @_undoable_assembly_edit("Move element up")
    def _on_move_lens_up(self) -> None:
        """Move lens up in system."""
        current = self._system_list.currentRow()
        if current > 0:
            (
                self._optical_system.elements[current],
                self._optical_system.elements[current - 1],
            ) = (
                self._optical_system.elements[current - 1],
                self._optical_system.elements[current],
            )
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()

    @_undoable_assembly_edit("Move element down")
    def _on_move_lens_down(self) -> None:
        """Move lens down in system."""
        current = self._system_list.currentRow()
        if current >= 0 and current < len(self._optical_system.elements) - 1:
            (
                self._optical_system.elements[current],
                self._optical_system.elements[current + 1],
            ) = (
                self._optical_system.elements[current + 1],
                self._optical_system.elements[current],
            )
            self._update_system_list()
            self._assembly_viz.update_system(self._optical_system)
            self._on_assembly_changed()

    def _on_system_item_selected(self, index: int) -> None:
        """Handle system item selection.

        Args:
            index: Row index of the element selected in the system list;
                enables the air gap editor for rows after the first element.
        """
        if index > 0:
            self._air_gap_group.setEnabled(True)
            # The gap before the element at 'index' is at index-1 in the air_gaps list
            gap_index = index - 1
            if gap_index < len(self._optical_system.air_gaps):
                gap_obj = self._optical_system.air_gaps[gap_index]
                gap_value = gap_obj.thickness if isinstance(gap_obj, AirGap) else gap_obj
                self._air_gap_input.blockSignals(True)
                self._air_gap_input.setValue(gap_value)
                self._air_gap_input.blockSignals(False)
            else:
                self._air_gap_group.setEnabled(False)
        else:
            self._air_gap_group.setEnabled(False)

        # Alignment editor follows the selected element (any row, incl. 0).
        elements = self._optical_system.elements
        if 0 <= index < len(elements):
            self._align_group.setEnabled(True)
            element = elements[index]
            self._decenter_y_input.blockSignals(True)
            self._decenter_z_input.blockSignals(True)
            self._decenter_y_input.setValue(element.decenter_y or 0.0)
            self._decenter_z_input.setValue(element.decenter_z or 0.0)
            self._decenter_y_input.blockSignals(False)
            self._decenter_z_input.blockSignals(False)
            for spin, attr in zip(self._tilt_inputs, ("tilt_x", "tilt_y", "tilt_z")):
                spin.blockSignals(True)
                spin.setValue(getattr(element, attr, 0.0) or 0.0)
                spin.blockSignals(False)
        else:
            self._align_group.setEnabled(False)

    def _on_apply_gap_clicked(self) -> None:
        """Apply the current air gap value to the system."""
        self._on_air_gap_changed(self._air_gap_input.value())

    @_undoable_assembly_edit("Edit air gap")
    def _on_air_gap_changed(self, value: float) -> None:
        """Update air gap for selected element.

        Args:
            value: New air gap thickness in mm, applied to the gap before the
                element currently selected in the system list.
        """
        current = self._system_list.currentRow()
        if current >= 0:
            # The gap before the i-th element is at index i-1 in self.air_gaps
            gap_index = current - 1
            if gap_index >= 0 and gap_index < len(self._optical_system.air_gaps):
                gap_obj = self._optical_system.air_gaps[gap_index]
                if isinstance(gap_obj, AirGap):
                    gap_obj.thickness = value
                else:
                    self._optical_system.air_gaps[gap_index] = value

                # Update positions in the optical system
                self._optical_system._update_positions()

                self._update_system_list()
                self._assembly_viz.update_system(self._optical_system)
                self._on_assembly_changed()

    def _on_assembly_changed(self) -> None:
        """Notify parent window of assembly changes."""
        self._parent._current_assembly = self._optical_system
        self._parent._update_status(f"Assembly updated: {self._optical_system.name}")
        self.data_updated.emit()

    def refresh(self) -> None:
        """Refresh assembly tab state from parent's current assembly.

        Reloads the lens list and syncs the builder with the parent window's
        current lens/system state.  A genuine system switch clears undo
        history; a refresh of the same system leaves it alone.
        """
        self.refresh_lens_list()

        current = getattr(self._parent, "_current_assembly", None)
        if current is not None:
            if current is not self._optical_system:
                self.load_system(current)
            else:
                self._refresh_assembly_ui()
        elif self._optical_system is not None:
            # The window no longer has an assembly.  Keep the last drawing on
            # screen (the delete path clears it explicitly), but never let a
            # stale history survive into another model.
            self._undo_stack.clear()
            self._assembly_viz.update_system(self._optical_system)
