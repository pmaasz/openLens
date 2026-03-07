# AGENTS.md - AI Coding Agent Instructions for OpenLens

This file provides guidance for AI coding agents working in this repository.

## Project Overview

OpenLens is an interactive optical lens design and simulation tool for single glass lens elements.
- **Language**: Python 3.6+
- **License**: MIT
- **Core Dependencies**: Standard library only (tkinter, json, math, unittest). **IMPORTANT**: Always prefer the standard library over external dependencies.
- **Optional Dependencies**: matplotlib, numpy, scipy, Pillow (for advanced features). **RULE**: Only use these if explicitly requested or if performance requirements cannot be met with standard Python.

## Project Structure

```
/src/               # Main source code (30 modules)
/tests/             # Test suites (34 test files)
/docs/              # Documentation
/openlens.py        # Main GUI entry point
/setup.py           # Package distribution
/requirements.txt   # Dependencies
```

Key source files:
- `src/lens.py` - Core Lens class model
- `src/lens_editor.py` - CLI application and LensManager
- `src/lens_editor_gui.py` - GUI application (tkinter)
- `src/aberrations.py` - Aberrations calculator
- `src/ray_tracer.py` - Ray tracing engine
- `src/validation.py` - Input validation utilities
- `src/services.py` - Service layer (business logic)
- `src/constants.py` - All constants and configuration

## Build/Lint/Test Commands

### Running the Application
```bash
python3 openlens.py              # Run GUI application
python3 -m src.lens_editor       # Run CLI application
```

### Running Tests
```bash
# Run all tests
python3 tests/run_all_tests.py

# Run specific test file
python3 tests/test_lens_editor.py
python3 tests/test_gui.py

# Run a single test method
python3 -m unittest tests.test_lens_editor.TestLensCalculations.test_biconvex_focal_length

# With pytest (if installed)
pytest tests/                           # All tests
pytest tests/test_lens_editor.py        # Single file
pytest tests/test_lens_editor.py::TestLensCalculations::test_biconvex_focal_length  # Single test
pytest --cov=src tests/                 # With coverage
```

### Linting
```bash
pre-commit run --all-files    # Run all pre-commit hooks
black src/ tests/ --check     # Check formatting
flake8 src/ tests/            # Run linter
```

### Installation
```bash
pip install -e .              # Install package
pip install -e .[dev]         # Install with dev dependencies
```

## Code Style Guidelines

### Naming Conventions
- **Classes**: `PascalCase` (e.g., `LensRayTracer`, `AberrationsCalculator`)
- **Functions/methods**: `snake_case` (e.g., `calculate_focal_length`, `get_lens_by_id`)
- **Constants**: `UPPER_SNAKE_CASE` (e.g., `DEFAULT_RADIUS_1`, `EPSILON`)
- **Private methods**: `_leading_underscore` (e.g., `_calculate_geometry`, `_validate_input`)
- **Test methods**: `test_<what>_<condition>_<expected_result>`

### Import Organization
Organize imports in 3 groups with blank lines between:

```python
# 1. Standard library imports
import math
import json
from typing import Optional, Dict, Any, List, Tuple

# 2. Third-party imports (if any)
import numpy as np

# 3. Local imports with try/except for relative import fallback
try:
    from .constants import EPSILON, DEFAULT_RADIUS_1
    from .validation import validate_positive
except ImportError:
    from constants import EPSILON, DEFAULT_RADIUS_1
    from validation import validate_positive
```

### Type Hints
Use type hints consistently with the `typing` module:
```python
def calculate_focal_length(self) -> Optional[float]:
    ...

def get_lens(self, lens_id: int) -> Optional[Dict[str, Any]]:
    ...

def trace_rays(self, rays: List[Tuple[float, float]]) -> List[Dict[str, float]]:
    ...
```

### Docstrings
Use Google-style docstrings:
```python
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
```

### Formatting
- **Line length**: 100 characters maximum
- **Formatter**: black (configured in pre-commit)
- **Linter**: flake8 (ignores E203, W503)

## Error Handling Patterns

### Custom Exceptions
```python
class ValidationError(Exception):
    """Raised when validation fails."""
    pass
```

### Graceful Degradation for Optional Dependencies
```python
try:
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False
```

### Validation with Descriptive Errors
```python
if radius <= 0:
    raise ValidationError(
        f"Radius must be positive, got {radius}. "
        "Use negative values for concave surfaces."
    )
```

### Return None for Undefined Calculations
```python
def calculate_focal_length(self) -> Optional[float]:
    if abs(power) < EPSILON:
        return None  # Infinite focal length (afocal system)
    return 1.0 / power
```

### Logging for Non-Critical Errors
```python
logger.warning("Validation error: %s", e)
logger.error("Error updating lens: %s", e)
```

## Testing Guidelines

- Use `unittest` framework (standard library)
- Structure tests with `setUp()`, `tearDown()`, `test_<description>()`
- Use `tempfile.NamedTemporaryFile` for temporary files
- Prefer specific assertions: `assertEqual`, `assertAlmostEqual`, `assertIsNone`, `assertRaises`

```python
class TestLensCalculations(unittest.TestCase):
    def setUp(self):
        self.lens = Lens(radius_1=50.0, radius_2=-50.0, n=1.5, thickness=5.0)

    def test_biconvex_focal_length_positive(self):
        """Biconvex lens should have positive focal length."""
        focal_length = self.lens.calculate_focal_length()
        self.assertGreater(focal_length, 0)
        self.assertAlmostEqual(focal_length, 50.0, places=1)

    def test_invalid_radius_raises_validation_error(self):
        """Invalid radius should raise ValidationError."""
        with self.assertRaises(ValidationError):
            Lens(radius_1=0, radius_2=-50.0, n=1.5, thickness=5.0)
```

## Key Constants (from src/constants.py)

- `EPSILON = 1e-10` - Tolerance for floating-point comparisons
- `DEFAULT_RADIUS_1 = 100.0` - Default first surface radius (mm)
- `DEFAULT_RADIUS_2 = -100.0` - Default second surface radius (mm)
- `DEFAULT_THICKNESS = 10.0` - Default lens thickness (mm)
- `DEFAULT_REFRACTIVE_INDEX = 1.5168` - Default glass refractive index (BK7)

## Common Patterns

### Service Layer Pattern
Business logic is in `src/services.py`, keeping UI code thin:
```python
# In GUI/CLI code
result = services.calculate_lens_properties(lens_data)
```

### Validation Before Processing
Always validate inputs before calculations:
```python
def process_lens(self, data: Dict[str, Any]) -> Lens:
    validated = self.validator.validate_lens_data(data)
    return Lens(**validated)
```

## Context-Aware Reminders

### When Editing `src/*.py` Files

**Before making changes:**
- Read the existing code to understand the module's purpose
- Check for existing patterns in the file (logging, validation, etc.)

**During changes:**
- Use `logger.info()`, `logger.warning()`, `logger.error()` instead of `print()` statements
- Import constants from `src/constants.py` - don't hardcode magic numbers
- Add type hints to all function signatures
- Write Google-style docstrings for all public functions

**After changes:**
- Run the test suite: `python3 tests/run_all_tests.py`
- If adding new functionality, add corresponding tests in `tests/`
- Verify no regressions were introduced

**Logging setup example:**
```python
import logging

logger = logging.getLogger(__name__)

def my_function():
    logger.info("Starting operation")
    # ... code ...
    logger.warning("Potential issue: %s", details)
```

### When Editing `docs/**/*.rst` Files

**Before making changes:**
- Understand RST syntax (indentation matters!)
- Check the document's place in the table of contents (`index.rst`)

**During changes:**
- Use proper RST heading hierarchy (consistent underline characters)
- Ensure blank lines before and after directives
- Use `:ref:` for internal cross-references, `:doc:` for document links
- Validate Python code examples are syntactically correct

**After changes:**
- Check RST syntax is valid
- Verify cross-references point to existing targets
- Run doc-checker if available

**RST heading hierarchy:**
```rst
===================
Top Level (Chapter)
===================

Section
-------

Subsection
^^^^^^^^^^

Subsubsection
"""""""""""""
```

### When Editing `tests/*.py` Files

**Before making changes:**
- Review existing test structure in the file
- Understand what module/functionality is being tested

**During changes:**
- Follow naming convention: `test_<what>_<condition>_<expected_result>`
- Use `setUp()` and `tearDown()` for test fixtures
- Use specific assertions: `assertEqual`, `assertAlmostEqual`, `assertRaises`
- Use `tempfile.NamedTemporaryFile` for temporary files (auto-cleanup)

**After changes:**
- Run the specific test file: `python3 -m unittest tests.test_<name>`
- Run the full suite to catch any interactions: `python3 tests/run_all_tests.py`

**Test structure example:**
```python
class TestFeatureName(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        self.instance = MyClass()

    def tearDown(self):
        """Clean up after tests."""
        pass

    def test_method_valid_input_returns_expected(self):
        """Method should return expected result for valid input."""
        result = self.instance.method(valid_input)
        self.assertEqual(result, expected_value)

    def test_method_invalid_input_raises_error(self):
        """Method should raise ValidationError for invalid input."""
        with self.assertRaises(ValidationError):
            self.instance.method(invalid_input)
```

## Automation Subagents

This project has automation subagents configured in `.opencode/agents/`:

### quality-checker
- **Purpose**: Run tests, formatters (black), and linters (flake8)
- **When to use**: After editing `src/` or `tests/` files, before committing
- **Command**: Checks formatting, runs linter, and invokes `python3 tests/run_all_tests.py`

### doc-checker
- **Purpose**: Validate Sphinx documentation
- **When to use**: After editing `docs/sphinx/source/` files
- **Validates**: RST syntax, cross-references, Python code examples

### commit
- **Purpose**: Create well-formatted git commits
- **When to use**: After completing a feature, fix, or documentation change
- **Features**: Analyzes changes, generates conventional commit messages, stages files safely
- **Safety**: Never commits secrets, never force pushes, reviews changes first
