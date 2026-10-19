# Repository facts and environment quirks

## Remotes and branches

- `origin` = `git@github.com:pmaasz/openLens.git`, authenticated as `pmaasz`.
- Base branch is **`master`**, not `main`.
- `master` has no branch protection, but the convention is still: green CI
  before merge, squash merge, branch deleted on merge.

## `gh` quirks in this environment

**`gh issue view <n>` fails** with:

```
GraphQL: Projects (classic) is being deprecated ...
```

That is `gh` requesting the retired `projectCards` field. Always use
`--json`:

```bash
gh issue view 470 --json number,title,body,labels,url
gh issue list --label bug --state open --json number,title,labels
gh pr view 12 --json number,title,url,mergeable   # same failure without --json
```

**`gh pr edit` fails the same way**, because it also requests `projectCards`.
There is no `--json` escape hatch for a write, so update the PR body over REST:

```bash
python3 -c "
import json
json.dump({'body': open('/tmp/pr-body.md').read()}, open('/tmp/prbody.json','w'))"
gh api -X PATCH repos/pmaasz/openLens/pulls/510 --input /tmp/prbody.json
```

Note `gh api` accepts **one** argument after the flag set — `--input file --jq
.number` parses as two positional args and errors with `accepts 1 arg(s)`.
Keep the trailing selector inside the same `--jq` value.

## Interpreting the issue body

Bodies follow a consistent shape:

- `**Where:**` - `file:line` list. Read these first.
- A bulleted list of concrete defects.
- `**Fix:**` - the intended direction of the fix.

Most bodies enumerate several distinct defects. Treat each bullet as something
the PR must resolve, and check them off one by one before opening the PR.

## Local vs CI test runs

Local (system `python3`, 3.12) has: PySide6, matplotlib, numpy.
It does **not** have: pytest, scipy, Pillow.

`python3 -m unittest discover -s tests -t .` therefore reports six
pre-existing loader errors that are **not** regressions:

```
ERROR: tests.gui_flows.test_assembly_optimization_flow (unittest.loader._FailedTest...)
ERROR: tests.gui_flows.test_exports_theme_flow ...
ERROR: tests.gui_flows.test_lens_editor_flow ...
ERROR: tests.gui_flows.test_persistence_library_flow ...
ERROR: tests.gui_flows.test_simulation_performance_flow ...
ERROR: tests.gui_flows.test_visual_regression ...
```

Cause: `tests/gui_flows/conftest.py` imports `pytest`, which is not installed
locally. CI installs pytest and runs those files separately.

### The local suite has a *different set of packages* than CI

Local `python3` has PySide6, numpy, matplotlib, **and setuptools**. The CI
runner installs the project with `pip install -e .[dev]` into a fresh
interpreter, and pip builds in an **isolated environment** — so `setuptools` is
used to build the package but is never installed alongside it. It is
**not importable** where the tests run.

So a test that imports `setuptools` (to read packaging metadata, say) passes
locally and errors in CI with `ModuleNotFoundError: No module named
'setuptools'`.

`build` and `wheel` are absent both locally and in CI, so nothing that wants to
build a distribution will work without adding it.

**Do not `skipUnless` a dependency just because CI lacks it** — if the test
exists to check something CI does not otherwise check, skipping it in CI leaves
the gap open while reporting green. Either avoid the dependency, or add it to
CI. This is exactly how #470 shipped: nothing built or inspected a real install,
so a missing console script went unnoticed.

Corollary: because the local suite always reports 6 errors, it is easy to stop
reading its output. A local error count that is *neither* the 6-error baseline
nor 0 — CI reported 4 for #470 — is a strong signal that the environments have
diverged, not that the change is fine.

Baseline on a clean `master`:

```
Ran 1576 tests in ~235s
FAILED (errors=6, skipped=31)
```

Judge your change by *delta*: same 6 errors, no new ones.

GUI flow QA (`make qa`, `make qa-gui`, `make qa-visual`) needs pytest and
therefore only runs in CI. If a bug is GUI-only, lean on CI for that layer.

## Tooling

```bash
black    # /home/philip/.local/bin/black
flake8   # /home/philip/.local/bin/flake8   (.venv/bin/flake8 also present)
pytest   # not installed locally
```

## CI jobs (`.github/workflows/ci.yml`)

| Job | Blocking? | Notes |
| --- | --- | --- |
| Lint | yes for `black` | flake8 and pre-commit are `continue-on-error` |
| Test (py3.10/3.11/3.12) | yes | quick suite, then full suite |
| Coverage | yes | the long pole, ~10 min |
| Docs | yes | Sphinx build must succeed |
| Build | yes | `python -m build` + `twine check` |

Total wall time ~12 min. Every job gates `master`.

Editing anything under `docs/sphinx/source/` can break the Docs job - build it
locally first with `cd docs/sphinx && make html`.

## Release automation

`release-please` watches `master` and parses Conventional Commits
(`fix:` -> patch, `feat:` -> minor while <1.0, `BREAKING CHANGE:` -> major).
Commit subjects therefore need a real conventional prefix and a scope where one
fits: `fix(io):`, `fix(gui):`, `fix(physics):`, `perf(gui):`, `refactor(...)`.

## Gitignore traps

Already ignored, never stage: `*.db`, `data/`, `specs/`, `dist/`, `build/`,
`*.egg-info/`, `.venv/`, `venv/`, `.idea/`, `__pycache__/`, `.pytest_cache/`.

Check `git status` before every commit. Real databases in the working tree
(`openlens.db`, `lenses.db`) hold user data - never delete or commit them.

## Tests live in `tests/`

Roughly 56 modules mirroring `openlens/`. Match the existing module for the code
under test and follow its `setUp`/`test_<what>_<condition>_<result>` style.
`tests/gui_flows/` holds pytest-based user-flow QA with visual regression.