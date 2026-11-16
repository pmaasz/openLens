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

:meth:`LensOptimizer.optimize_damped_least_squares` is the Levenberg-Marquardt
solver: it differentiates the target residuals numerically, solves the damped
normal equations, and raises the damping when a trial is rejected. It respects
variable bounds, keeps the best accepted design when a step fails, and is the
better choice for merit functions with many, correlated variables.
