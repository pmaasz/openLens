Tolerancing Tab
===============

.. automodule:: openlens.gui.tabs.tolerancing_tab
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

``TolerancingTab`` defines tolerance operands and runs sensitivity or Monte
Carlo analysis. Workers perturb a deep copy of the active model, so a run cannot
write perturbed values back to the SQLite library.

The tab reports nominal, worst-case, and statistical performance together with
the assumptions used for compensators and focus adjustment.
