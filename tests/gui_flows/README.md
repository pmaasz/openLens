# GUI Flow QA (replaces manual click-through)

Automated coverage for the 12 manual user flows in `openlens.py:OpenLensWindow`.
Headless-safe (`QT_QPA_PLATFORM=offscreen`), hermetic temp DB per test.

## Layout

- `conftest.py` — offscreen setup, `main_window` fixture (temp SQLite, no prod DB touch)
- `pages.py` — `MainWindowPO` page object (reads like the manual checklist)
- `snapshots.py` — visual regression harness (`__snapshots__/` baselines, lenient thresholds)
- `test_*_flow.py` — functional flows (lens editor, simulation/performance,
  assembly/optimization/tolerancing, persistence/library, exports/theme)
- `test_visual_regression.py` — viz widgets + full-window tab screenshots

## Run

```bash
pip install -e .[dev]          # pulls pytest-qt, pytest-xdist
QT_QPA_PLATFORM=offscreen pytest tests/gui_flows -v
QT_QPA_PLATFORM=offscreen pytest tests/gui_flows -n auto   # parallel
make qa      # full: unit + flows + visuals
make qa-gui  # flows only
```

## Manual checklist mapping

| Manual click-through | Automated test |
|---|---|
| New lens / edit R1/R2/thickness | `test_lens_editor_flow.py::test_create_and_edit_lens_flow` |
| Duplicate, tab switching (6 tabs) | `test_lens_editor_flow.py::test_duplicate_and_tab_switching_flow` |
| Simulation Run/Clear/Reset, ghosts | `test_simulation_performance_flow.py` |
| Calculate Metrics, PSF/MTF/Wavefront/Ghost | `test_simulation_performance_flow.py` |
| Assembly add/gap/move/remove | `test_assembly_optimization_flow.py::test_assembly_builder_flow` |
| Optimization variables + run | `test_assembly_optimization_flow.py::test_optimization_collect_and_fast_run_flow` |
| Tolerancing defaults + Monte Carlo | `test_assembly_optimization_flow.py::test_tolerancing_*` |
| Edit persistence, save/reload, menu switch, delete guard | `test_persistence_library_flow.py` |
| Save As, STL/SVG/report, STEP graceful, theme/view | `test_exports_theme_flow.py` |
| Eyeball every viz / tab | `test_visual_regression.py` + `__snapshots__/` |

## Visual baselines

First run bootstraps `__snapshots__/*.png` and passes. Commit baselines.
Later runs fail only on significant drift; diffs land in
`/tmp/openlens_qa_failures/` (uploaded as CI artifacts). Blank renders always fail.
Thresholds are per-target: viz widgets use strict defaults (mean 8/255, 5%
pixels) since they are mostly vector graphics; full main-window shots use
lenient thresholds (mean 15/255, 15% pixels) because platform text
antialiasing differs across Qt/fontconfig versions.
