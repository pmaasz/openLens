# OpenLense Testing Guide

This document describes the functional tests for the OpenLense application.

## Test Files

- **test_lens_editor.py** - Core functionality tests for the Lens class and LensManager
- **test_gui.py** - GUI functionality tests for the graphical editor
- **run_all_tests.py** - Master test runner that executes all test suites

## Running Tests

### Run All Tests
```bash
python3 run_all_tests.py
```

### Run Only Core Tests
```bash
python3 test_lens_editor.py
```

### Run Only GUI Tests
```bash
python3 test_gui.py
```

## Test Coverage

### Core Functionality Tests (24 tests)

#### TestLens (9 tests)
- ✓ Lens creation with default parameters
- ✓ Lens creation with custom parameters
- ✓ Lens serialization to dictionary
- ✓ Lens deserialization from dictionary
- ✓ Focal length calculation for biconvex lens
- ✓ Focal length calculation for plano-convex lens
- ✓ Focal length with zero radius (edge case)
- ✓ Focal length with no optical power (edge case)
- ✓ String representation formatting

#### TestLensManager (6 tests)
- ✓ Manager initialization
- ✓ Saving lenses to file
- ✓ Loading lenses from file
- ✓ Loading from non-existent file (error handling)
- ✓ Loading from corrupt JSON file (error handling)
- ✓ Getting lens by index with boundary checks
- ✓ Multiple lenses persistence

#### TestLensCalculations (4 tests)
- ✓ Symmetric biconvex focal length calculation
- ✓ High refractive index material calculation
- ✓ Converging lens positive focal length
- ✓ Different front and back curvatures

#### TestDataIntegrity (5 tests)
- ✓ Unique lens ID generation
- ✓ Valid ISO timestamp format
- ✓ Extreme value handling
- ✓ Complete JSON serialization
- ✓ Deserialization with missing fields

### GUI Functionality Tests (17 tests)

#### TestGUILensEditor (14 tests)
- ✓ GUI initialization
- ✓ Form variable creation
- ✓ Default value assignment
- ✓ Form clearing functionality
- ✓ Loading lens data to form
- ✓ Saving new lens
- ✓ Updating existing lens
- ✓ Lens list refresh
- ✓ Focal length calculation in GUI
- ✓ Invalid input handling for calculations
- ✓ Zero radius handling
- ✓ Auto-update modified timestamp
- ✓ Lens duplication
- ✓ Status bar updates

#### TestGUIDataPersistence (1 test)
- ✓ Save and load through GUI

#### TestGUIValidation (2 tests)
- ✓ Invalid numeric input validation
- ✓ Empty name default handling

## Test Results

**Total Tests: 41**
- Core Tests: 24/24 ✓
- GUI Tests: 17/17 ✓

All tests passing! ✓✓✓

## What's Being Tested

### Lens Physics
- Lensmaker's equation calculation accuracy
- Optical power calculations
- Different lens type behaviors (converging, diverging)
- Material refractive index effects

### Data Management
- JSON serialization/deserialization
- File persistence
- Data integrity
- Unique ID generation
- Timestamp management

### Error Handling
- Invalid numeric inputs
- Missing data files
- Corrupt JSON files
- Zero/infinite values
- Boundary conditions

### GUI Functionality
- Widget initialization
- Form operations (clear, load, save)
- User input validation
- Real-time calculations
- Status updates
- List management

### Edge Cases
- Extreme parameter values
- Missing fields in data
- Zero radius of curvature
- Flat surfaces (plano lenses)
- High refractive index materials

## Continuous Testing

These tests should be run:
1. After any code changes
2. Before committing to version control
3. As part of deployment verification
4. When adding new features

## Adding New Tests

To add new tests, follow this pattern:

```python
class TestNewFeature(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        # Initialize test data
        pass
    
    def tearDown(self):
        """Clean up after tests"""
        # Remove temporary files
        pass
    
    def test_feature_behavior(self):
        """Test description"""
        # Arrange
        # Act
        # Assert
        pass
```

Then add the test class to the appropriate test file's test suite.
