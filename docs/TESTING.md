# OpenLens Testing

> **The authoritative guide is the Testing section of
> [`docs/sphinx/source/contributing.rst`](sphinx/source/contributing.rst).**
> This file is kept for links to `docs/TESTING.md`.

## Install test dependencies

```bash
pip install -e .[dev]
```

`pytest-qt` from the dev extra is required for the GUI flow tests.

## Run the unit suite

```bash
python3 -m unittest discover -s tests -t .
```

Slow Monte Carlo, end-to-end, and functional-optimizer suites can be skipped:

```bash
OPENLENS_SKIP_SLOW=1 python3 -m unittest discover -s tests -t .
```

## Run a single module or test

```bash
python3 -m unittest tests.test_validation
python3 -m unittest tests.test_validation.TestRadiusValidation.test_valid_radius_returns_float
```

## Run with pytest

```bash
pytest tests/
pytest tests/test_validation.py
pytest -n auto tests/          # requires pytest-xdist
```

## GUI flow tests

```bash
QT_QPA_PLATFORM=offscreen pytest tests/gui_flows -q
```

Tests redirect application data into a temporary per-run directory through
`tests/__init__.py`, so they do not touch the user's SQLite library.

## Before opening a pull request

```bash
black --line-length=100 --check openlens/ tests/
flake8 openlens/ tests/
python3 -m unittest discover -s tests -t .
```
