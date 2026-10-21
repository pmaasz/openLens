Optimizer
=========

.. automodule:: openlens.optimizer
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

``LensOptimizer`` combines variables, targets, and a merit function. Prefer the
high-level :meth:`LensOptimizer.optimize` wrapper: it selects the best available
algorithm (simplex by default) and handles invalid geometries with penalties.
