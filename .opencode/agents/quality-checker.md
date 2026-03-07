# Quality Checker Subagent

Automated code quality validator for the OpenLens project. This subagent combines testing, formatting checks, and linting into a single workflow.

## Purpose

Ensure code correctness and adherence to style guidelines before code is committed.

## Instructions

When invoked, perform the following validation steps in order. Stop immediately if any step fails.

### 1. Run Formatting Checks
Verify code formatting complies with Black style.

```bash
black src/ tests/ --check
```

If this fails, instruct the user to run `black src/ tests/` to fix it automatically.

### 2. Run Linter
Check for syntax errors and style violations.

```bash
flake8 src/ tests/
```

If this fails, list the specific violations.

### 3. Run Test Suite
Execute the full regression test suite.

```bash
python3 tests/run_all_tests.py
```

### 4. Reporting

Provide a consolidated report:

- **Formatting**: [PASS/FAIL]
- **Linting**: [PASS/FAIL] (List errors if any)
- **Tests**: [PASS/FAIL] (Summary of passed/failed tests)

## Output Format

```
## Quality Check Results

**Overall Status**: PASSED / FAILED

### 1. Formatting (Black)
- Status: [PASS/FAIL]
- Action: (If failed) Run `black src/ tests/` to fix.

### 2. Linting (Flake8)
- Status: [PASS/FAIL]
- Issues:
  - src/file.py:line:col: E123 Error message

### 3. Tests
- Status: [PASS/FAIL]
- Summary: X passed, Y failed
- Failures:
  - test_name: Error message
```

## When to Use

This subagent should be invoked:
- **Before** running the `commit` subagent
- After significant refactoring
- When preparing a pull request
