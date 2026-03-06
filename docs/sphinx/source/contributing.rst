Contributing
============

Thank you for your interest in contributing to OpenLens! This guide will help you get started.

Development Setup
-----------------

1. Fork and clone the repository:

.. code-block:: bash

    git clone https://github.com/yourusername/openLens.git
    cd openLens

2. Create a virtual environment:

.. code-block:: bash

    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate

3. Install development dependencies:

.. code-block:: bash

    pip install -e .[dev]

4. Install pre-commit hooks:

.. code-block:: bash

    pre-commit install

Code Style
----------

OpenLens follows these conventions:

Naming Conventions
^^^^^^^^^^^^^^^^^^

- **Classes**: ``PascalCase`` (e.g., ``LensRayTracer``, ``AberrationsCalculator``)
- **Functions/methods**: ``snake_case`` (e.g., ``calculate_focal_length``)
- **Constants**: ``UPPER_SNAKE_CASE`` (e.g., ``DEFAULT_RADIUS_1``)
- **Private methods**: ``_leading_underscore`` (e.g., ``_validate_input``)

Import Organization
^^^^^^^^^^^^^^^^^^^

Organize imports in three groups:

.. code-block:: python

    # 1. Standard library
    import math
    import json
    from typing import Optional, Dict, Any

    # 2. Third-party (if any)
    import numpy as np

    # 3. Local imports
    from .constants import EPSILON, DEFAULT_RADIUS_1
    from .validation import validate_positive

Type Hints
^^^^^^^^^^

Use type hints consistently:

.. code-block:: python

    def calculate_focal_length(self) -> Optional[float]:
        ...

    def get_lens(self, lens_id: int) -> Optional[Dict[str, Any]]:
        ...

Docstrings
^^^^^^^^^^

Use Google-style docstrings:

.. code-block:: python

    def calculate_power(radius_1: float, radius_2: float, n: float) -> float:
        """Calculate the optical power of a lens.

        Args:
            radius_1: Radius of curvature of the first surface (mm).
            radius_2: Radius of curvature of the second surface (mm).
            n: Refractive index of the lens material.

        Returns:
            Optical power in diopters.

        Raises:
            ValidationError: If any parameter is invalid.
        """

Formatting
^^^^^^^^^^

- **Line length**: 100 characters maximum
- **Formatter**: black
- **Linter**: flake8

Run formatters before committing:

.. code-block:: bash

    black src/ tests/
    flake8 src/ tests/

Running Tests
-------------

Run All Tests
^^^^^^^^^^^^^

.. code-block:: bash

    python tests/run_all_tests.py

Or with pytest:

.. code-block:: bash

    pytest tests/

Run Specific Tests
^^^^^^^^^^^^^^^^^^

.. code-block:: bash

    # Single test file
    pytest tests/test_lens_editor.py

    # Single test method
    pytest tests/test_lens_editor.py::TestLensCalculations::test_biconvex_focal_length

With Coverage
^^^^^^^^^^^^^

.. code-block:: bash

    pytest --cov=src tests/
    pytest --cov=src --cov-report=html tests/

Writing Tests
-------------

Test Structure
^^^^^^^^^^^^^^

Use ``unittest`` framework with descriptive test names:

.. code-block:: python

    class TestLensCalculations(unittest.TestCase):
        def setUp(self):
            """Set up test fixtures."""
            self.lens = Lens(
                radius_1=50.0,
                radius_2=-50.0,
                n=1.5,
                thickness=5.0
            )

        def test_biconvex_focal_length_positive(self):
            """Biconvex lens should have positive focal length."""
            focal_length = self.lens.calculate_focal_length()
            self.assertGreater(focal_length, 0)
            self.assertAlmostEqual(focal_length, 50.0, places=1)

        def test_invalid_radius_raises_validation_error(self):
            """Invalid radius should raise ValidationError."""
            with self.assertRaises(ValidationError):
                Lens(radius_1=0, radius_2=-50.0, n=1.5, thickness=5.0)

Test Naming Convention
^^^^^^^^^^^^^^^^^^^^^^

Name tests as: ``test_<what>_<condition>_<expected_result>``

Examples:

- ``test_focal_length_biconvex_positive``
- ``test_validation_zero_radius_raises_error``
- ``test_ray_trace_parallel_rays_converge``

Project Structure
-----------------

.. code-block:: text

    openLens/
    ├── src/                    # Main source code
    │   ├── lens.py            # Core Lens class
    │   ├── ray_tracer.py      # Ray tracing engine
    │   ├── aberrations.py     # Aberration calculations
    │   ├── validation.py      # Input validation
    │   ├── constants.py       # Constants and configuration
    │   ├── services.py        # Service layer
    │   ├── lens_editor.py     # CLI application
    │   ├── lens_editor_gui.py # GUI application
    │   └── gui/               # GUI components package
    │       ├── tabs/          # Tab implementations
    │       ├── tooltip.py     # Tooltip widget
    │       ├── theme.py       # Theme management
    │       └── storage.py     # Persistence utilities
    ├── tests/                  # Test suites
    ├── docs/                   # Documentation
    │   └── sphinx/            # Sphinx documentation
    ├── openlens.py            # Main entry point
    └── setup.py               # Package distribution

Pull Request Process
--------------------

1. Create a feature branch:

.. code-block:: bash

    git checkout -b feature/your-feature-name

2. Make your changes and add tests

3. Ensure all tests pass:

.. code-block:: bash

    python tests/run_all_tests.py

4. Run pre-commit hooks:

.. code-block:: bash

    pre-commit run --all-files

5. Commit with a descriptive message:

.. code-block:: bash

    git commit -m "Add feature: description of what and why"

6. Push and create a pull request

Reporting Issues
----------------

When reporting issues, please include:

- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Any error messages or stack traces

Feature Requests
----------------

Feature requests are welcome! Please describe:

- The problem you're trying to solve
- Your proposed solution
- Any alternatives you've considered

License
-------

By contributing to OpenLens, you agree that your contributions will be licensed under the MIT License.
