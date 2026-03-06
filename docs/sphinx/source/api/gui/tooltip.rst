Tooltip
=======

.. automodule:: src.gui.tooltip
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ToolTip class provides hover tooltips for tkinter widgets.

Example Usage
-------------

.. code-block:: python

    from src.gui.tooltip import ToolTip
    import tkinter as tk

    root = tk.Tk()
    button = tk.Button(root, text="Hover me")
    button.pack()

    # Add tooltip to button
    ToolTip(button, "This is a helpful tooltip")

    root.mainloop()
