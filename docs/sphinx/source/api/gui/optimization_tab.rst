Optimization Tab
================

.. automodule:: openlens.gui.tabs.optimization_tab
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

``OptimizationTab`` exposes optimization variables and targets for a lens or
system. The default path is :meth:`openlens.optimizer.LensOptimizer.optimize`,
which selects the simplex algorithm unless the caller requests another one.

The merit function penalizes invalid geometry such as negative edge thickness.
Results are applied to the live model only after a run succeeds.
