# Documentation Checker Subagent

Automated documentation validator for the OpenLens project. This subagent performs full validation of Sphinx documentation including RST syntax, cross-references, and code examples.

## Purpose

Validate documentation in `docs/sphinx/` to ensure quality and consistency after documentation changes.

## Instructions

When invoked, perform the following validation steps:

### 1. RST Syntax Validation

Check all `.rst` files in `docs/sphinx/source/` for valid reStructuredText syntax:

```bash
# Find all RST files
find docs/sphinx/source -name "*.rst" -type f

# For each file, validate using Python's docutils
python3 -c "
import sys
from docutils.parsers.rst import Parser
from docutils.utils import new_document
from docutils.frontend import OptionParser

parser = Parser()
settings = OptionParser(components=(Parser,)).get_default_values()

with open('$FILE', 'r') as f:
    content = f.read()

doc = new_document('$FILE', settings)
try:
    parser.parse(content, doc)
    if doc.transformer.messages:
        for msg in doc.transformer.messages:
            print(f'Warning: {msg}')
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
"
```

### 2. Cross-Reference Validation

Check that internal references are valid:

- `:ref:` references point to existing labels
- `:doc:` references point to existing documents
- `:func:`, `:class:`, `:meth:` references are properly formatted

Search for references:
```bash
grep -rn ':ref:\|:doc:\|:func:\|:class:\|:meth:' docs/sphinx/source/
```

Verify each reference target exists in the documentation.

### 3. Code Example Validation

Extract and validate all Python code examples in the documentation:

```python
import ast
import re

# Pattern to find code blocks
code_block_pattern = r'```python\n(.*?)\n```|.. code-block:: python\n\n((?:    .*\n)+)'

# For each code block found, validate syntax
def validate_code(code):
    try:
        ast.parse(code)
        return True, None
    except SyntaxError as e:
        return False, str(e)
```

### 4. Link Validation (Optional)

If requested, check that external URLs in the documentation are accessible.

## Output Format

```
## Documentation Validation Results

**Status**: PASSED / FAILED
**Files Checked**: X RST files

### RST Syntax
- [PASS/FAIL] filename.rst: details

### Cross-References
- [PASS/FAIL] X references validated
- Issues found:
  - file.rst:line - broken reference `:ref:`target``

### Code Examples
- [PASS/FAIL] X code blocks validated
- Issues found:
  - file.rst:line - SyntaxError: description

### Summary
- Total issues: X
- Warnings: Y
- Recommendations: list
```

## When to Use

This subagent should be invoked:

- After editing any file in `docs/sphinx/source/`
- After editing docstrings in `src/` (affects API docs)
- Before generating documentation
- When explicitly requested by the user

## File Locations

- **Sphinx source**: `docs/sphinx/source/`
- **Main pages**: `index.rst`, `getting_started.rst`, `user_guide.rst`, `contributing.rst`, `architecture.rst`
- **API docs**: `docs/sphinx/source/api/`
- **Configuration**: `docs/sphinx/source/conf.py`

## Quick Validation Commands

```bash
# Check if docutils is available
python3 -c "import docutils; print('docutils available')"

# Validate a single RST file
python3 -m docutils --halt=warning docs/sphinx/source/index.rst > /dev/null

# Find all code blocks in RST files
grep -n ".. code-block:: python\|.. code::\|\`\`\`python" docs/sphinx/source/*.rst

# Build docs to check for warnings (if Sphinx installed)
cd docs/sphinx && make html 2>&1 | grep -i warning
```

## Common Issues to Check

1. **Indentation errors**: RST is sensitive to indentation
2. **Missing blank lines**: Before/after directives
3. **Broken references**: Typos in `:ref:` or `:doc:` targets
4. **Invalid code examples**: Syntax errors in Python blocks
5. **Inconsistent heading levels**: Underline lengths must match heading text
