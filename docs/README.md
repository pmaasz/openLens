# OpenLens Documentation

This directory contains the documentation for OpenLens.

## Primary Documentation (Sphinx)

The primary documentation is built with Sphinx and located in `sphinx/`. To view 
the documentation:

### Build and View Locally

```bash
cd docs/sphinx
make html
open build/html/index.html  # macOS
xdg-open build/html/index.html  # Linux
```

### Documentation Structure

The Sphinx documentation includes:

- **Getting Started** - Installation and quick start guide
- **User Guide** - Comprehensive usage guide including ray tracing
- **Architecture** - System design and module organization
- **Contributing** - How to contribute, coding standards, testing
- **API Reference** - Auto-generated API documentation

## Legacy Markdown Files

The following Markdown files are kept for reference but their content has been 
migrated to the Sphinx documentation:

| File | Migrated To |
|------|-------------|
| `CONTRIBUTING.md` | `sphinx/source/contributing.rst` |
| `ARCHITECTURE.md` | `sphinx/source/architecture.rst` |
| `TESTING.md` | `sphinx/source/contributing.rst` (Testing section) |
| `RAY_TRACING_GUIDE.md` | `sphinx/source/user_guide.rst` (Ray Tracing section) |
| `API_DOCUMENTATION.md` | `sphinx/source/api/` (auto-generated) |

### Technical Reference Files

These files contain detailed implementation notes that supplement the main 
documentation:

- `RAYTRACING_IMPLEMENTATION.md` - Technical ray tracing algorithm details
- `FEATURE_ABERRATIONS.md` - Aberration calculation implementation
- `FEATURES_IMPLEMENTED.md` - Feature implementation history
- `FEATURES_SUMMARY.md` - High-level feature overview

### Project History Files

- `SESSION_ACCOMPLISHMENTS.md` - Development session notes
- `REFACTORING_SUMMARY.md` - Code refactoring history
- `PROJECT_SUMMARY.md` - Project overview and status

## Building Documentation

### Prerequisites

```bash
pip install sphinx sphinx-rtd-theme
```

### Build Commands

```bash
cd docs/sphinx

# Build HTML documentation
make html

# Build PDF (requires LaTeX)
make latexpdf

# Clean build artifacts
make clean
```

## Contributing to Documentation

See `sphinx/source/contributing.rst` for documentation contribution guidelines.

When adding new documentation:

1. Add new RST files to `sphinx/source/`
2. Include them in the appropriate `toctree` directive
3. Follow the existing style and formatting conventions
4. Build and verify the documentation renders correctly
