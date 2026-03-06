# Test Runner Subagent

Automated test runner for the OpenLens project. This subagent runs the test suite and reports results.

## Purpose

Run after code changes to `src/` files to ensure no regressions are introduced.

## Instructions

When invoked, perform the following steps:

### 1. Run the Test Suite

Execute the full test suite using the project's test runner:

```bash
python3 tests/run_all_tests.py
```

### 2. Parse and Report Results

After running tests, provide a summary that includes:

- **Total tests run**: Count from output
- **Passed**: Number of successful tests
- **Failed**: Number of failed tests (if any)
- **Errors**: Number of tests with errors (if any)
- **Execution time**: How long the tests took

### 3. Failure Analysis

If any tests fail:

1. List each failing test by name
2. Show the assertion error or exception message
3. Identify which file/function the test covers
4. Suggest potential causes based on recent changes

### 4. Success Confirmation

If all tests pass:

- Confirm with a brief success message
- Report the total count (e.g., "All 41 tests passed in 2.3s")

## Output Format

```
## Test Results

**Status**: PASSED / FAILED
**Summary**: X/Y tests passed (Z failures, W errors)
**Duration**: X.Xs

### Failures (if any)
- `test_name`: Error message
  - File: `tests/test_file.py:line`
  - Likely cause: description

### Recommendations (if failures)
- Specific suggestions for fixing failures
```

## When to Use

This subagent should be invoked:

- After editing any file in `src/`
- After editing any file in `tests/`
- Before committing changes
- When explicitly requested by the user

## Test Command Reference

```bash
# Full test suite (recommended)
python3 tests/run_all_tests.py

# Single test file
python3 -m unittest tests.test_lens_editor

# Single test method
python3 -m unittest tests.test_lens_editor.TestLensCalculations.test_biconvex_focal_length

# With pytest (if available)
pytest tests/ -v
```
