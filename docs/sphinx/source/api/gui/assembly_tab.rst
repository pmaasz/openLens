Assembly Tab
============

.. automodule:: openlens.gui.tabs.assembly_tab
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

``AssemblyTab`` edits an :class:`openlens.optical_system.OpticalSystem`: element
order, air gaps, aperture stop, decenter/tilt, and nested assembly groups.

Every structural edit is recorded on a snapshot-based ``QUndoStack``. A
window-level ``QUndoGroup`` switches between the lens editor and assembly stacks
so **Undo** and **Redo** always apply to the active workspace.
