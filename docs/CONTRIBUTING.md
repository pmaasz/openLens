# Contributing to OpenLens

> **The authoritative guide is
> [`docs/sphinx/source/contributing.rst`](sphinx/source/contributing.rst).**
> This file is kept as a short entry point for links to `docs/CONTRIBUTING.md`.

## Set up

```bash
git clone https://github.com/pmaasz/openLens.git
cd openLens
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e .[dev]
pre-commit install
```

PySide6 is required. numpy and matplotlib enable plotting and most analysis;
scipy and Pillow enable advanced diffraction and image simulation.

## Design a change

- Open or claim an issue before large features.
- Keep the optical core independent of Qt. A calculator should be testable
  without a display.
- Write the test first where practical. Tests use `unittest`; GUI flows use
  `pytest-qt`.
- Import constants from `openlens/constants.py`; do not hardcode physical
  constants.
- Optional dependencies must stay behind availability flags.

## Check the change

```bash
black --line-length=100 openlens/ tests/
flake8 openlens/ tests/
python3 -m unittest discover -s tests -t .
QT_QPA_PLATFORM=offscreen pytest tests/gui_flows -q
```

For documentation changes, also build Sphinx:

```bash
cd docs/sphinx
make html
```

## Pull requests

- Use a conventional-commit title, for example
  `fix(gui): keep mount changes on the undo stack`.
- Link the issue in the body.
- Add the appropriate type and `prio-*` labels.
- Keep the PR focused; file unrelated follow-up work as a separate issue.
- A PR is merged only when CI is green.

See the Sphinx contributing page for coding standards, test structure, commit
guidance, and the review process.
