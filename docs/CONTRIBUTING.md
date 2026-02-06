# Contributing to openlens

Thank you for your interest in contributing to openlens! This document provides comprehensive guidelines for contributing to the project.

---

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)
- [Issue Guidelines](#issue-guidelines)
- [Community](#community)

---

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors, regardless of experience level, background, or identity.

### Expected Behavior

- ✅ Be respectful and considerate in all interactions
- ✅ Welcome newcomers and help them get started
- ✅ Provide constructive feedback
- ✅ Focus on what is best for the project and community
- ✅ Show empathy towards other contributors

### Unacceptable Behavior

- ❌ Harassment, discrimination, or offensive comments
- ❌ Personal attacks or trolling
- ❌ Publishing others' private information
- ❌ Other conduct inappropriate in a professional setting

### Enforcement

Violations can be reported to the project maintainers. All reports will be reviewed and investigated promptly and fairly.

---

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.6+** installed
- **Git** for version control
- **tkinter** for GUI development
- **Optional**: matplotlib, numpy for advanced features
- A **GitHub account**

### First Time Contributors

New to open source? Great! Here's how to start:

1. **Find a beginner-friendly issue**: Look for issues tagged with `good-first-issue` or `help-wanted`
2. **Read the documentation**: Familiarize yourself with the [README](../README.md) and [API docs](API_DOCUMENTATION.md)
3. **Set up your environment**: Follow the development setup below
4. **Ask questions**: Don't hesitate to ask for help in issues or discussions

---

## Development Setup

### 1. Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/YOUR_USERNAME/openLens.git
cd openLens

# Add upstream remote
git remote add upstream https://github.com/ORIGINAL_OWNER/openLens.git
```

### 2. Create Virtual Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate it
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Install optional dependencies for full functionality
pip install matplotlib numpy

# For development, install testing tools
pip install pytest pytest-cov

# Verify installation
python3 verify_setup.py
```

### 4. Run Tests

```bash
# Run all tests to ensure everything works
python3 tests/run_all_tests.py

# Should see: "All 41 tests passed!"
```

### 5. Create a Branch

```bash
# Create a descriptive branch name
git checkout -b feature/my-new-feature
# or
git checkout -b fix/bug-description
```

---

## How to Contribute

### Types of Contributions

#### 🐛 Bug Fixes

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

**Example Bug Fix Checklist:**
- [ ] Issue created or referenced
- [ ] Bug reproduced and understood
- [ ] Fix implemented with minimal changes
- [ ] Test added to prevent regression
- [ ] Documentation updated if needed
- [ ] All tests pass

#### ✨ New Features

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

**Example Feature Checklist:**
- [ ] Feature discussed and approved in issue
- [ ] Code follows project architecture
- [ ] Comprehensive tests added
- [ ] API documentation written
- [ ] User guide updated (if GUI feature)
- [ ] Example code provided
- [ ] Performance tested
- [ ] All existing tests still pass

#### 📚 Documentation

Documentation improvements are always welcome:

- **Fix typos and grammar**
- **Clarify confusing sections**
- **Add examples**
- **Improve API documentation**
- **Create tutorials**
- **Translate to other languages** (future)

**Documentation Checklist:**
- [ ] Changes are accurate
- [ ] Examples are tested
- [ ] Formatting is consistent
- [ ] Links work correctly

#### 🎨 UI/UX Improvements

Enhancing the user interface:

- **Better layouts**
- **Improved tooltips**
- **Color scheme refinements**
- **Keyboard shortcuts**
- **Accessibility improvements**

**UI Change Checklist:**
- [ ] Screenshot/mockup provided
- [ ] Maintains visual consistency
- [ ] Tested on multiple screen sizes
- [ ] Keyboard navigation works
- [ ] Tooltips are helpful

#### 🧪 Tests

Improve test coverage:

- **Add missing unit tests**
- **Add integration tests**
- **Add validation tests** (compare to known results)
- **Performance benchmarks**

**Test Contribution Checklist:**
- [ ] Tests are independent (no dependencies on order)
- [ ] Tests are deterministic (same result every time)
- [ ] Good test names (descriptive)
- [ ] Tests run quickly (<1s per test ideally)

---

## Coding Standards

### Python Style Guide

We follow **PEP 8** with some modifications:

#### Naming Conventions

```python
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
```

#### Code Formatting

```python
# Line length: 100 characters (flexible to 120)
# Use 4 spaces for indentation (no tabs)

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
```

#### Documentation Strings

```python
def calculate_optical_power(focal_length):
    """
    Calculate optical power in diopters.
    
    Args:
        focal_length (float): Focal length in millimeters
    
    Returns:
        float: Optical power in diopters (D)
    
    Raises:
        ValueError: If focal_length is zero
    
    Example:
        >>> power = calculate_optical_power(100.0)
        >>> print(f"{power:.2f} D")
        10.00 D
    """
    if focal_length == 0:
        raise ValueError("Focal length cannot be zero")
    return 1000.0 / focal_length
```

#### Import Organization

```python
# Standard library imports first
import os
import sys
from datetime import datetime

# Third-party imports
import numpy as np
import matplotlib.pyplot as plt

# Local imports
from lens_editor import Lens
from material_database import get_material_database
```

#### Comments

```python
# Use comments for WHY, not WHAT
# Good:
# Apply thin lens approximation since thickness < 1% of radius
power = (n - 1) * (1/R1 - 1/R2)

# Bad:
# Calculate power
power = (n - 1) * (1/R1 - 1/R2)

# Use inline comments sparingly
focal_length = 1 / power  # Units: mm
```

### Code Organization

#### File Structure

```python
#!/usr/bin/env python3
"""
Module docstring explaining purpose.

Detailed description if needed.
"""

# Imports
import ...

# Constants
CONSTANT_VALUE = 42

# Classes
class MyClass:
    pass

# Functions
def my_function():
    pass

# Main execution
if __name__ == "__main__":
    main()
```

#### Class Design

```python
class Lens:
    """A single optical lens element."""
    
    def __init__(self, name, radius1, radius2):
        """Initialize lens with parameters."""
        # Public attributes
        self.name = name
        self.radius1 = radius1
        self.radius2 = radius2
        
        # Private attributes
        self._cached_focal_length = None
    
    def calculate_focal_length(self):
        """Calculate and cache focal length."""
        if self._cached_focal_length is None:
            self._cached_focal_length = self._compute_focal_length()
        return self._cached_focal_length
    
    def _compute_focal_length(self):
        """Internal calculation method."""
        # Implementation
        pass
```

### Error Handling

```python
# Be specific with exceptions
# Good:
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
```

---

## Testing Requirements

### Test Structure

```python
#!/usr/bin/env python3
"""
Test suite for lens calculations.
"""

import unittest
from lens_editor import Lens

class TestLensCalculations(unittest.TestCase):
    """Test focal length calculations."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.lens = Lens(
            name="Test Lens",
            radius_of_curvature_1=100.0,
            radius_of_curvature_2=-100.0,
            thickness=5.0
        )
    
    def test_biconvex_focal_length(self):
        """Test focal length for biconvex lens."""
        focal_length = self.lens.calculate_focal_length()
        self.assertAlmostEqual(focal_length, 97.58, places=2)
    
    def test_negative_radius_raises_no_error(self):
        """Test that negative radius is valid."""
        lens = Lens(radius_of_curvature_1=-50.0)
        # Should not raise exception
        focal_length = lens.calculate_focal_length()
        self.assertIsNotNone(focal_length)
    
    def tearDown(self):
        """Clean up after tests."""
        pass

if __name__ == "__main__":
    unittest.main()
```

### Test Guidelines

#### What to Test

- ✅ **Happy path**: Normal expected usage
- ✅ **Edge cases**: Boundary values (0, negative, infinity)
- ✅ **Error conditions**: Invalid input handling
- ✅ **Integration**: Modules working together
- ✅ **Regression**: Previously fixed bugs

#### What NOT to Test

- ❌ Third-party library internals
- ❌ Python built-in functionality
- ❌ Trivial getters/setters

#### Test Naming

```python
# Pattern: test_<what>_<condition>_<expected_result>

def test_focal_length_biconvex_positive_value(self):
    """Test that biconvex lens produces positive focal length."""
    pass

def test_calculate_power_zero_focal_length_raises_error(self):
    """Test that zero focal length raises ValueError."""
    pass
```

#### Assertions

```python
# Use appropriate assertion methods
self.assertEqual(a, b)           # Exact equality
self.assertAlmostEqual(a, b, places=2)  # Float comparison
self.assertTrue(condition)
self.assertFalse(condition)
self.assertIsNone(value)
self.assertRaises(ValueError, func, args)
self.assertIn(item, container)
self.assertGreater(a, b)
```

### Running Tests

```bash
# Run all tests
python3 tests/run_all_tests.py

# Run specific test file
python3 tests/test_lens_editor.py

# Run with coverage (if pytest installed)
pytest --cov=src tests/

# Run single test method
python3 -m unittest tests.test_lens_editor.TestLensCalculations.test_biconvex_focal_length
```

### Test Coverage Goals

- **Core calculations**: 100% coverage
- **New features**: Must include tests
- **Bug fixes**: Must include regression test
- **Overall project**: Maintain >80% coverage

---

## Documentation

### Documentation Requirements

All contributions should include appropriate documentation:

#### Code Documentation

```python
# Module-level docstring
"""
Ray tracing module for optical simulation.

This module provides classes and functions for tracing light rays
through optical elements using Snell's law and vector mathematics.
"""

# Class docstring
class RayTracer:
    """
    Trace rays through optical systems.
    
    The RayTracer class handles ray propagation through lenses,
    applying physical laws of refraction and reflection.
    
    Attributes:
        lens (Lens): The lens to trace rays through
        wavelength (float): Wavelength of light in nm
    
    Example:
        >>> tracer = RayTracer(my_lens)
        >>> rays = tracer.trace_parallel_rays(num_rays=21)
    """

# Method docstring
def trace_ray(self, ray):
    """
    Trace a single ray through the lens.
    
    Args:
        ray (Ray): Initial ray to trace
    
    Returns:
        Ray: Ray with updated path after tracing
    
    Raises:
        ValueError: If ray direction is not normalized
    """
```

#### User Documentation

For user-facing features, update:

1. **README.md**: If feature is prominent
2. **API_DOCUMENTATION.md**: For API changes
3. **Examples**: Add usage examples
4. **CHANGELOG.md**: Document the change

#### Documentation Style

- **Clear and concise**: Avoid jargon where possible
- **Examples**: Show don't just tell
- **Diagrams**: Use ASCII art or images for complex concepts
- **Links**: Cross-reference related documentation

---

## Pull Request Process

### Before Submitting

Complete this checklist:

- [ ] **Code complete**: Feature/fix is fully implemented
- [ ] **Tests added**: New code has tests
- [ ] **Tests pass**: All tests run successfully
- [ ] **Documentation updated**: API docs, user guide, etc.
- [ ] **Code reviewed**: Self-review for obvious issues
- [ ] **Branch updated**: Rebased on latest main/master
- [ ] **Commits clean**: Logical, well-described commits

### Creating the PR

1. **Push your branch**:
   ```bash
   git push origin feature/my-feature
   ```

2. **Open PR on GitHub**:
   - Go to the repository
   - Click "New Pull Request"
   - Select your branch
   - Fill out the template

3. **PR Title**: Clear and descriptive
   ```
   Good: "Add chromatic aberration calculator"
   Good: "Fix ray tracing edge case for plano-convex lenses"
   Bad: "Update code"
   Bad: "Fix bug"
   ```

4. **PR Description**: Include:
   - **What**: What does this PR do?
   - **Why**: Why is this change needed?
   - **How**: How does it work?
   - **Testing**: How was it tested?
   - **Screenshots**: For UI changes
   - **Related Issues**: Closes #123

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Related Issues
Closes #<issue_number>

## How Has This Been Tested?
Describe the tests you ran

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
```

### Review Process

1. **Automated checks**: GitHub Actions run tests
2. **Code review**: Maintainer reviews code
3. **Feedback**: Address review comments
4. **Approval**: Once approved, PR is merged

### After Merge

- **Delete branch**: Clean up your feature branch
- **Update local**: 
  ```bash
  git checkout main
  git pull upstream main
  ```
- **Celebrate**: You've contributed! 🎉

---

## Issue Guidelines

### Creating Issues

#### Bug Reports

Use this template:

```markdown
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

**Screenshots**
If applicable, add screenshots

**Environment:**
 - OS: [e.g., Ubuntu 22.04]
 - Python Version: [e.g., 3.10.5]
 - openlens Version: [e.g., 2.0.0]

**Additional context**
Any other relevant information
```

#### Feature Requests

```markdown
**Is your feature request related to a problem?**
A clear description of the problem

**Describe the solution you'd like**
What you want to happen

**Describe alternatives you've considered**
Other approaches you've thought about

**Use case**
Who would benefit from this feature and how?

**Additional context**
Mockups, examples, etc.
```

### Issue Labels

We use these labels:

- `bug`: Something isn't working
- `enhancement`: New feature or request
- `documentation`: Documentation improvements
- `good-first-issue`: Good for newcomers
- `help-wanted`: Extra attention needed
- `question`: Further information requested
- `wontfix`: Will not be worked on
- `duplicate`: Already exists
- `priority-high`: High priority

---

## Community

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas
- **Pull Requests**: Code review and discussion

### Getting Help

- **Documentation**: Check docs/ folder first
- **Search Issues**: Your question might be answered
- **Ask Questions**: Open a discussion or issue
- **Be Patient**: Maintainers are volunteers

### Recognition

Contributors are recognized in:
- **README.md**: Contributors section
- **CHANGELOG.md**: Credits for changes
- **Release Notes**: Major contributions highlighted

---

## Development Workflow

### Typical Workflow

```bash
# 1. Update your fork
git checkout main
git pull upstream main
git push origin main

# 2. Create feature branch
git checkout -b feature/new-feature

# 3. Make changes
# ... edit files ...

# 4. Test frequently
python3 tests/run_all_tests.py

# 5. Commit changes
git add .
git commit -m "Add new feature description"

# 6. Push to your fork
git push origin feature/new-feature

# 7. Create PR on GitHub

# 8. Address review feedback
# ... make changes ...
git add .
git commit -m "Address review comments"
git push origin feature/new-feature

# 9. After merge, clean up
git checkout main
git pull upstream main
git branch -d feature/new-feature
git push origin --delete feature/new-feature
```

### Commit Messages

Follow these conventions:

```
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

---

fix: Correct sign convention in ray tracing

Ray refraction was using incorrect normal vector orientation
for concave surfaces. Fixed by normalizing towards center of
curvature.

Fixes #78

---

docs: Update API documentation for material database

Added examples for temperature-dependent refractive index
and Sellmeier coefficient usage.
```

---

## Advanced Topics

### Setting Up Pre-commit Hooks

```bash
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
```

### Debugging Tips

```python
# Use logging instead of print
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug(f"Ray direction: {direction}")
logger.info("Calculation complete")
logger.warning("Aperture might be too small")
logger.error("Ray tracing failed")
```

### Performance Profiling

```python
# Profile your code
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
```

---

## Resources

### Learning Resources

- **Python**: [Python.org Tutorial](https://docs.python.org/3/tutorial/)
- **Git**: [Pro Git Book](https://git-scm.com/book/en/v2)
- **Optics**: Hecht's "Optics" textbook
- **Testing**: [Python unittest docs](https://docs.python.org/3/library/unittest.html)

### Similar Projects

Study these for inspiration:
- **Zemax/OpticStudio**: Professional optical design
- **FRED**: Photon engineering software
- **Oslo**: Lens design software

---

## Questions?

Still have questions? Feel free to:

- 📝 Open an issue with the `question` label
- 💬 Start a discussion on GitHub Discussions
- 📧 Contact the maintainers (check README for contact info)

---

## Thank You!

Your contributions make openlens better for everyone. Whether you're fixing a typo, adding a feature, or reporting a bug, your effort is appreciated! 🙏

**Happy Contributing!** 🚀

---

**Document Version:** 1.0  
**Last Updated:** February 2026  
**Maintained by:** openlens Development Team
