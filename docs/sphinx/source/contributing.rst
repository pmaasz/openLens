Contributing
============

Thank you for your interest in contributing to OpenLens! This comprehensive guide 
covers everything you need to know to contribute effectively.

.. contents:: Table of Contents
   :local:
   :depth: 2

Code of Conduct
---------------

Our Pledge
^^^^^^^^^^

We are committed to providing a welcoming and inclusive environment for all 
contributors, regardless of experience level, background, or identity.

Expected Behavior
^^^^^^^^^^^^^^^^^

- Be respectful and considerate in all interactions
- Welcome newcomers and help them get started
- Provide constructive feedback
- Focus on what is best for the project and community
- Show empathy towards other contributors

Unacceptable Behavior
^^^^^^^^^^^^^^^^^^^^^

- Harassment, discrimination, or offensive comments
- Personal attacks or trolling
- Publishing others' private information
- Other conduct inappropriate in a professional setting

Enforcement
^^^^^^^^^^^

Violations can be reported to the project maintainers. All reports will be 
reviewed and investigated promptly and fairly.

Getting Started
---------------

Prerequisites
^^^^^^^^^^^^^

Before contributing, ensure you have:

- **Python 3.6+** installed
- **Git** for version control
- **tkinter** for GUI development
- **Optional**: matplotlib, numpy for advanced features
- A **GitHub account**

First Time Contributors
^^^^^^^^^^^^^^^^^^^^^^^

New to open source? Here's how to start:

1. **Find a beginner-friendly issue**: Look for issues tagged with ``good-first-issue`` or ``help-wanted``
2. **Read the documentation**: Familiarize yourself with the project structure
3. **Set up your environment**: Follow the development setup below
4. **Ask questions**: Don't hesitate to ask for help in issues or discussions

Development Setup
-----------------

1. Fork and Clone
^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Fork the repository on GitHub, then:
   git clone https://github.com/YOUR_USERNAME/openLens.git
   cd openLens

   # Add upstream remote
   git remote add upstream https://github.com/ORIGINAL_OWNER/openLens.git

2. Create Virtual Environment
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Create virtual environment
   python3 -m venv venv

   # Activate it
   # On Linux/macOS:
   source venv/bin/activate

   # On Windows:
   venv\Scripts\activate

3. Install Dependencies
^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Install package in development mode
   pip install -e .

   # Install with development dependencies
   pip install -e .[dev]

   # Or install optional dependencies individually
   pip install matplotlib numpy

   # Verify installation
   python3 verify_setup.py

4. Install Pre-commit Hooks
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   pre-commit install

5. Run Tests
^^^^^^^^^^^^

.. code-block:: bash

   # Run all tests to ensure everything works
   python3 tests/run_all_tests.py

   # Should see: "All tests passed!"

6. Create a Branch
^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Create a descriptive branch name
   git checkout -b feature/my-new-feature
   # or
   git checkout -b fix/bug-description

How to Contribute
-----------------

Types of Contributions
^^^^^^^^^^^^^^^^^^^^^^

Bug Fixes
"""""""""

Found a bug? Here's how to fix it:

1. **Check existing issues**: Search for similar bug reports
2. **Create an issue**: If it doesn't exist, describe the bug with:
   
   - Steps to reproduce
   - Expected behavior
   - Actual behavior
   - Your environment (OS, Python version)

3. **Fix the bug**: Write code to fix it
4. **Add tests**: Ensure the bug doesn't happen again
5. **Submit PR**: Reference the issue number

**Bug Fix Checklist:**

- Issue created or referenced
- Bug reproduced and understood
- Fix implemented with minimal changes
- Test added to prevent regression
- Documentation updated if needed
- All tests pass

New Features
""""""""""""

Want to add a feature? Follow this process:

1. **Discuss first**: Open an issue to discuss the feature
   
   - Explain the use case
   - Describe proposed solution
   - Get maintainer feedback

2. **Design**: Think about:
   
   - API design
   - Integration with existing code
   - Performance implications
   - User experience

3. **Implement**: Write the code
4. **Test thoroughly**: Unit tests + integration tests
5. **Document**: Add API docs and examples
6. **Submit PR**: With detailed description

**Feature Checklist:**

- Feature discussed and approved in issue
- Code follows project architecture
- Comprehensive tests added
- API documentation written
- User guide updated (if GUI feature)
- Example code provided
- Performance tested
- All existing tests still pass

Documentation
"""""""""""""

Documentation improvements are always welcome:

- Fix typos and grammar
- Clarify confusing sections
- Add examples
- Improve API documentation
- Create tutorials

UI/UX Improvements
""""""""""""""""""

Enhancing the user interface:

- Better layouts
- Improved tooltips
- Color scheme refinements
- Keyboard shortcuts
- Accessibility improvements

Tests
"""""

Improve test coverage:

- Add missing unit tests
- Add integration tests
- Add validation tests (compare to known results)
- Performance benchmarks

Coding Standards
----------------

Python Style Guide
^^^^^^^^^^^^^^^^^^

We follow **PEP 8** with some modifications.

Naming Conventions
""""""""""""""""""

.. code-block:: python

   # Classes: PascalCase
   class LensCalculator:
       pass

   # Functions and methods: snake_case
   def calculate_focal_length():
       pass

   # Constants: UPPER_SNAKE_CASE
   MAX_RADIUS = 1000.0

   # Private methods: leading underscore
   def _internal_helper():
       pass

   # Variables: snake_case
   focal_length = 100.0
   radius_of_curvature = 50.0

Code Formatting
"""""""""""""""

- **Line length**: 100 characters (flexible to 120)
- **Indentation**: 4 spaces (no tabs)
- **Formatter**: black
- **Linter**: flake8

.. code-block:: python

   # Good:
   def calculate_focal_length(radius1, radius2, thickness, 
                              refractive_index):
       """Calculate focal length using lensmaker's equation."""
       power = (refractive_index - 1) * (1/radius1 - 1/radius2)
       return 1 / power if power != 0 else float('inf')

   # Bad:
   def calculate_focal_length(radius1,radius2,thickness,refractive_index):
       power=(refractive_index-1)*(1/radius1-1/radius2)
       return 1/power if power!=0 else float('inf')

Run formatters before committing:

.. code-block:: bash

   black src/ tests/
   flake8 src/ tests/

Import Organization
"""""""""""""""""""

Organize imports in three groups with blank lines between:

.. code-block:: python

   # 1. Standard library imports
   import os
   import sys
   from datetime import datetime

   # 2. Third-party imports
   import numpy as np
   import matplotlib.pyplot as plt

   # 3. Local imports
   from .constants import EPSILON, DEFAULT_RADIUS_1
   from .validation import validate_positive

Type Hints
""""""""""

Use type hints consistently:

.. code-block:: python

   def calculate_focal_length(self) -> Optional[float]:
       ...

   def get_lens(self, lens_id: int) -> Optional[Dict[str, Any]]:
       ...

   def trace_rays(self, rays: List[Tuple[float, float]]) -> List[Dict[str, float]]:
       ...

Docstrings
""""""""""

Use Google-style docstrings:

.. code-block:: python

   def calculate_power(radius_1: float, radius_2: float, n: float, thickness: float) -> float:
       """Calculate the optical power of a thick lens.

       Args:
           radius_1: Radius of curvature of the first surface (mm).
           radius_2: Radius of curvature of the second surface (mm).
           n: Refractive index of the lens material.
           thickness: Center thickness of the lens (mm).

       Returns:
           Optical power in diopters.

       Raises:
           ValidationError: If any parameter is invalid.
       """

Comments
""""""""

.. code-block:: python

   # Use comments for WHY, not WHAT
   # Good:
   # Apply thin lens approximation since thickness < 1% of radius
   power = (n - 1) * (1/R1 - 1/R2)

   # Bad:
   # Calculate power
   power = (n - 1) * (1/R1 - 1/R2)

   # Use inline comments sparingly
   focal_length = 1 / power  # Units: mm

Error Handling
^^^^^^^^^^^^^^

.. code-block:: python

   # Be specific with exceptions
   try:
       value = float(user_input)
   except ValueError as e:
       print(f"Invalid number: {e}")
       return None

   # Provide helpful error messages
   if radius <= 0:
       raise ValueError(
           f"Radius must be positive, got {radius}. "
           "Use negative values for concave surfaces."
       )

   # Use assertions for internal checks
   def calculate_power(focal_length):
       assert focal_length != 0, "Focal length cannot be zero"
       return 1000.0 / focal_length

Testing
-------

Running Tests
^^^^^^^^^^^^^

Run All Tests
"""""""""""""

.. code-block:: bash

   python3 tests/run_all_tests.py

Or with pytest:

.. code-block:: bash

   pytest tests/

Run Specific Tests
""""""""""""""""""

.. code-block:: bash

   # Single test file
   python3 tests/test_lens_editor.py

   # With pytest
   pytest tests/test_lens_editor.py

   # Single test method
   python3 -m unittest tests.test_lens_editor.TestLensCalculations.test_biconvex_focal_length

   # Or with pytest
   pytest tests/test_lens_editor.py::TestLensCalculations::test_biconvex_focal_length

With Coverage
"""""""""""""

.. code-block:: bash

   pytest --cov=src tests/
   pytest --cov=src --cov-report=html tests/

Test Structure
^^^^^^^^^^^^^^

Use ``unittest`` framework with descriptive test names:

.. code-block:: python

   import unittest
   from src.lens import Lens

   class TestLensCalculations(unittest.TestCase):
       """Test focal length calculations."""
       
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
       
       def tearDown(self):
           """Clean up after tests."""
           pass

   if __name__ == "__main__":
       unittest.main()

Test Naming Convention
""""""""""""""""""""""

Name tests as: ``test_<what>_<condition>_<expected_result>``

Examples:

- ``test_focal_length_biconvex_positive``
- ``test_validation_zero_radius_raises_error``
- ``test_ray_trace_parallel_rays_converge``

Test Guidelines
^^^^^^^^^^^^^^^

What to Test
""""""""""""

- **Happy path**: Normal expected usage
- **Edge cases**: Boundary values (0, negative, infinity)
- **Error conditions**: Invalid input handling
- **Integration**: Modules working together
- **Regression**: Previously fixed bugs

What NOT to Test
""""""""""""""""

- Third-party library internals
- Python built-in functionality
- Trivial getters/setters

Assertions
""""""""""

.. code-block:: python

   # Use appropriate assertion methods
   self.assertEqual(a, b)           # Exact equality
   self.assertAlmostEqual(a, b, places=2)  # Float comparison
   self.assertTrue(condition)
   self.assertFalse(condition)
   self.assertIsNone(value)
   self.assertRaises(ValueError, func, args)
   self.assertIn(item, container)
   self.assertGreater(a, b)

Test Coverage
^^^^^^^^^^^^^

Current test coverage includes:

**Core Functionality Tests (24+ tests)**

- Lens class: Creation, serialization, focal length calculations
- LensManager: File persistence, lens retrieval
- Data integrity: ID generation, JSON serialization

**GUI Functionality Tests (17+ tests)**

- Widget initialization and form operations
- User input validation
- Real-time calculations

**Analysis Tests**

- Ray tracing accuracy
- Aberration calculations
- Material database queries

**Coverage Goals:**

- **Core calculations**: 100% coverage
- **New features**: Must include tests
- **Bug fixes**: Must include regression test
- **Overall project**: Maintain >80% coverage

Pull Request Process
--------------------

Before Submitting
^^^^^^^^^^^^^^^^^

Complete this checklist:

- Code complete: Feature/fix is fully implemented
- Tests added: New code has tests
- Tests pass: All tests run successfully
- Documentation updated: API docs, user guide, etc.
- Code reviewed: Self-review for obvious issues
- Branch updated: Rebased on latest main/master
- Commits clean: Logical, well-described commits

Creating the PR
^^^^^^^^^^^^^^^

1. **Push your branch**:

   .. code-block:: bash

      git push origin feature/my-feature

2. **Open PR on GitHub**:
   
   - Go to the repository
   - Click "New Pull Request"
   - Select your branch
   - Fill out the template

3. **PR Title**: Clear and descriptive

   .. code-block:: text

      Good: "Add chromatic aberration calculator"
      Good: "Fix ray tracing edge case for plano-convex lenses"
      Bad: "Update code"
      Bad: "Fix bug"

4. **PR Description**: Include:
   
   - **What**: What does this PR do?
   - **Why**: Why is this change needed?
   - **How**: How does it work?
   - **Testing**: How was it tested?
   - **Screenshots**: For UI changes
   - **Related Issues**: Closes #123

PR Template
^^^^^^^^^^^

.. code-block:: markdown

   ## Description
   Brief description of changes

   ## Type of Change
   - [ ] Bug fix (non-breaking change which fixes an issue)
   - [ ] New feature (non-breaking change which adds functionality)
   - [ ] Breaking change (fix or feature that causes existing functionality to not work)
   - [ ] Documentation update

   ## Related Issues
   Closes #<issue_number>

   ## How Has This Been Tested?
   Describe the tests you ran

   ## Checklist
   - [ ] My code follows the style guidelines
   - [ ] I have performed a self-review
   - [ ] I have commented my code where needed
   - [ ] I have made corresponding changes to documentation
   - [ ] My changes generate no new warnings
   - [ ] I have added tests that prove my fix/feature works
   - [ ] New and existing unit tests pass locally

Review Process
^^^^^^^^^^^^^^

1. **Automated checks**: GitHub Actions run tests
2. **Code review**: Maintainer reviews code
3. **Feedback**: Address review comments
4. **Approval**: Once approved, PR is merged

After Merge
^^^^^^^^^^^

.. code-block:: bash

   # Delete your feature branch
   git checkout main
   git pull upstream main
   git branch -d feature/my-feature

Commit Messages
^^^^^^^^^^^^^^^

Follow these conventions:

.. code-block:: text

   # Format:
   <type>: <short summary> (50 chars or less)

   <optional body with more details>

   <optional footer with issue references>

   # Types:
   feat: New feature
   fix: Bug fix
   docs: Documentation changes
   style: Formatting, missing semicolons, etc.
   refactor: Code restructuring
   test: Adding tests
   chore: Maintenance tasks

   # Examples:
   feat: Add spherical aberration calculator

   Implements Seidel spherical aberration calculation using 
   surface contributions and ray height analysis.

   Closes #45

Issue Guidelines
----------------

Bug Reports
^^^^^^^^^^^

.. code-block:: markdown

   **Describe the bug**
   A clear description of what the bug is.

   **To Reproduce**
   Steps to reproduce:
   1. Open the application
   2. Click on '...'
   3. See error

   **Expected behavior**
   What you expected to happen

   **Actual behavior**
   What actually happened

   **Environment:**
    - OS: [e.g., Ubuntu 22.04]
    - Python Version: [e.g., 3.10.5]
    - OpenLens Version: [e.g., 2.0.0]

   **Additional context**
   Any other relevant information

Feature Requests
^^^^^^^^^^^^^^^^

.. code-block:: markdown

   **Is your feature request related to a problem?**
   A clear description of the problem

   **Describe the solution you'd like**
   What you want to happen

   **Describe alternatives you've considered**
   Other approaches you've thought about

   **Use case**
   Who would benefit from this feature and how?

Issue Labels
^^^^^^^^^^^^

- ``bug``: Something isn't working
- ``enhancement``: New feature or request
- ``documentation``: Documentation improvements
- ``good-first-issue``: Good for newcomers
- ``help-wanted``: Extra attention needed
- ``question``: Further information requested
- ``wontfix``: Will not be worked on
- ``duplicate``: Already exists
- ``priority-high``: High priority

Project Structure
-----------------

.. code-block:: text

   openLens/
   ├── openlens.py               # Main entry point
   ├── src/                      # Main source code
   │   ├── lens.py              # Core Lens class
   │   ├── lens_editor.py       # CLI application, LensManager
   │   ├── lens_editor_gui.py   # Main GUI application
   │   ├── ray_tracer.py        # Ray tracing engine
   │   ├── aberrations.py       # Aberration calculations
   │   ├── validation.py        # Input validation
   │   ├── constants.py         # Constants and configuration
   │   ├── services.py          # Service layer
   │   └── gui/                 # GUI components package
   │       ├── tabs/            # Tab implementations
   │       ├── tooltip.py       # Tooltip widget
   │       ├── theme.py         # Theme management
   │       └── storage.py       # Persistence utilities
   ├── tests/                   # Test suites
   ├── docs/                    # Documentation
   │   └── sphinx/              # Sphinx documentation
   └── setup.py                 # Package distribution

Advanced Topics
---------------

Setting Up Pre-commit Hooks
^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: bash

   # Create .git/hooks/pre-commit
   cat > .git/hooks/pre-commit << 'EOF'
   #!/bin/bash
   echo "Running tests before commit..."
   python3 tests/run_all_tests.py
   if [ $? -ne 0 ]; then
       echo "Tests failed. Commit aborted."
       exit 1
   fi
   EOF

   chmod +x .git/hooks/pre-commit

Debugging Tips
^^^^^^^^^^^^^^

.. code-block:: python

   # Use logging instead of print
   import logging
   logging.basicConfig(level=logging.DEBUG)
   logger = logging.getLogger(__name__)

   logger.debug(f"Ray direction: {direction}")
   logger.info("Calculation complete")
   logger.warning("Aperture might be too small")
   logger.error("Ray tracing failed")

Performance Profiling
^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

   import cProfile
   import pstats

   profiler = cProfile.Profile()
   profiler.enable()

   # Your code here
   result = lens.calculate_focal_length()

   profiler.disable()
   stats = pstats.Stats(profiler)
   stats.sort_stats('cumulative')
   stats.print_stats(10)  # Top 10 functions

Resources
---------

Learning Resources
^^^^^^^^^^^^^^^^^^

- **Python**: `Python.org Tutorial <https://docs.python.org/3/tutorial/>`_
- **Git**: `Pro Git Book <https://git-scm.com/book/en/v2>`_
- **Optics**: Hecht's "Optics" textbook
- **Testing**: `Python unittest docs <https://docs.python.org/3/library/unittest.html>`_

Similar Projects
^^^^^^^^^^^^^^^^

Study these for inspiration:

- **Zemax/OpticStudio**: Professional optical design
- **FRED**: Photon engineering software
- **Oslo**: Lens design software

Getting Help
^^^^^^^^^^^^

- **Documentation**: Check docs/ folder first
- **Search Issues**: Your question might be answered
- **Ask Questions**: Open a discussion or issue
- **Be Patient**: Maintainers are volunteers

License
-------

By contributing to OpenLens, you agree that your contributions will be licensed 
under the MIT License.
