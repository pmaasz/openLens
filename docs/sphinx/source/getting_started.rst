Getting Started
===============

This guide will help you get started with OpenLens, an interactive optical lens design and simulation tool.

Installation
------------

From Source
^^^^^^^^^^^

Clone the repository and install:

.. code-block:: bash

    git clone https://github.com/yourusername/openLens.git
    cd openLens
    pip install -e .

For development with all dependencies:

.. code-block:: bash

    pip install -e .[dev]

Requirements
^^^^^^^^^^^^

- Python 3.6 or higher
- tkinter (usually included with Python)

Optional dependencies for advanced features:

- matplotlib - Enhanced visualization
- numpy - Numerical computations  
- scipy - Advanced optical calculations
- Pillow - Image export

Quick Start
-----------

Running the GUI Application
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Launch the graphical interface:

.. code-block:: bash

    python openlens.py

This opens the main OpenLens window where you can:

- Design lens parameters interactively
- Run ray tracing simulations
- Analyze aberrations
- Export lens designs

Running the CLI Application
^^^^^^^^^^^^^^^^^^^^^^^^^^^

For command-line usage:

.. code-block:: bash

    python -m src.lens_editor

Basic Usage Example
-------------------

Creating a Lens Programmatically
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from src.lens import Lens

    # Create a biconvex lens
    lens = Lens(
        radius_1=50.0,      # First surface radius (mm)
        radius_2=-50.0,     # Second surface radius (mm)
        thickness=10.0,     # Center thickness (mm)
        diameter=25.0,      # Lens diameter (mm)
        n=1.5168           # Refractive index (BK7 glass)
    )

    # Calculate optical properties
    focal_length = lens.calculate_focal_length()
    print(f"Focal length: {focal_length:.2f} mm")

Ray Tracing
^^^^^^^^^^^

.. code-block:: python

    from src.ray_tracer import LensRayTracer

    # Create ray tracer for the lens
    tracer = LensRayTracer(lens)

    # Trace parallel rays
    rays = tracer.trace_parallel_rays(num_rays=11)

    # Access ray data
    for ray in rays:
        print(f"Ray at height {ray['start_y']:.2f} focuses at {ray['focus_x']:.2f}")

Aberration Analysis
^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from src.aberrations import AberrationsCalculator

    # Calculate aberrations
    calc = AberrationsCalculator(lens)
    aberrations = calc.calculate_all()

    print(f"Spherical aberration: {aberrations['spherical']:.4f}")
    print(f"Chromatic aberration: {aberrations['chromatic']:.4f}")

Next Steps
----------

- Read the :doc:`user_guide` for detailed feature documentation
- Explore the :doc:`api/index` for programmatic usage
- See :doc:`contributing` to contribute to the project
