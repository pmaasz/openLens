---
name: Code Review
description: Perform an evidence-based, full-repository code review and file every confirmed defect as a GitHub issue. Use when asked to review the codebase, audit a subsystem, sweep for bugs, or "find everything wrong and open tickets". Findings are reproduced with scripts first, grouped by root cause, deduplicated against existing issues, and labelled with the repository's existing labels.
---

# Code Review

Turn a codebase into a stream of **reproducible, well-scoped GitHub issues**.
The unit of output is an issue that a maintainer can act on without redoing the
investigation: exact evidence, root cause with file:line, impact, and a concrete
fix direction.

This is not a style review. Do not file missing type hints, naming nits,
"could be cleaner" comments, or speculative refactors. Every filed issue must
correspond to observed behaviour that is wrong, lossy, crashing, or silently
misleading.

## Ground rules

1. **Reproduce before filing.** Every finding gets a standalone script (or a
   test) whose output demonstrates the defect. "Reading the code suggests..."
   is not a finding.
2. **Judge against the documented contract.** A function that accepts a
   parameter and ignores it, a save/load pair that does not round-trip, a
   tracer that stops responding to an input - those are defects. A design
   choice the project documents as intentional is not.
3. **Group by root cause, not by symptom.** One missing wavelength argument
   that breaks several call sites is one issue with several reproductions, not
   five issues.
4. **Deduplicate.** Search open *and* closed issues before filing. If a closed
   issue covers it, do not reopen the same complaint; file only a genuinely
   new failure mode and link the old issue.
5. **Use existing labels.** Run `gh label list` first. Never invent a label.
6. **No drive-by fixes.** The deliverable of this skill is issues (plus the
   skill/artifacts commit), not source changes. Fixes belong to the
   `bug-fix-loop` skill or a separate task.

## Phase 0 - Establish the baseline

A review is only credible if the suite is green before you start; otherwise
every later failure is ambiguous.

```bash
scripts/baseline.sh
```

The script records: git commit, branch, working-tree state, Python/test
interpreter, suite result, and lint result. Save the log under
`/tmp/opencode/review-baseline.log`. If the suite is already red, record the
pre-existing failures and exclude them from findings.

## Phase 1 - Map the surface

```bash
find . -name '*.py' -not -path './.venv/*' -not -path './.opencode/*' | wc -l
find tests -name 'test_*.py' | wc -l
git ls-files | sed 's#/[^/]*$##' | sort | uniq -c | sort -rn | head -30
```

Read `AGENTS.md` and the architecture docs. Build a short list of subsystems and
their entry points. Review breadth-first: one pass per subsystem, then deep-dive
where the code is most stateful or numerically sensitive.

Priority order for an optics/simulation repository:

1. Core model and persistence (round-trip, defaults, invariants).
2. Tracers and physics (wavelength, signs, units, alignment, apertures).
3. Analysis layers (spot/PSF/MTF/aberrations/ghosts/tolerancing).
4. IO and import/export (units, references, material resolution).
5. GUI wiring (signals, unit labels, save/load, worker threads).
6. Optimizers and caches (state restoration, invalidation, convergence).

## Phase 2 - Review passes

Run these passes over each subsystem. They catch different bug classes.

### A. Contract and round-trip

- Save → load → compare every field. Include `inf`, `NaN`, zero, `None`.
- Export → import → compare: radii, thickness, material, stop, tilt/decenter,
  wavelength, aperture, coatings.
- Check that a function's parameters are actually used; grep the body for each
  argument name.
- Check that a writer's output is accepted by its own reader, and that a
  validator does not reject the writer's own output.

### B. Physics and units

- Does every wavelength-dependent path use the requested wavelength?
- Are signs and coordinate conventions consistent between 2D and 3D?
- Are Petzval radius, focus shift, distortion, and spot size reported in the
  documented unit and quantity?
- Do limiting cases behave (tilt → 0, decenter → 0, aperture → 0, afocal)?
- Are `inf`/`None` handled without turning a perturbation into a no-op?

### C. State, caching, and failure paths

- Is mutable global/shared state restored in `finally`?
- Do caches have invalidation call sites in production, not just tests?
- Do exceptions get swallowed and return a plausible-looking wrong value?
- Are `nan`/`inf` prevented from entering results, or at least surfaced?

### D. IO and external formats

- Are references real references (STEP `#n`) and are the referenced entities
  emitted?
- Are units explicit and converted once?
- Are unknown materials/values rejected or preserved, never silently replaced
  by a default (e.g. BK7)?
- Is untrusted input size-capped and validated?

### E. GUI wiring

- Grep for each signal name: is it connected, and to a slot that exists?
- Do labels match the computed quantity/unit?
- Does a button path call a method that exists with the right signature?
- Are worker threads forbidden from touching widgets?

### F. Optional dependencies

- The app must start and run core features without optional packages.
- Guard imports with `try/except` plus a `*_AVAILABLE` flag; check the
  non-optional branch is exercised.

### G. Optimizers and merit functions

- For every target/variable name the GUI can produce, confirm the engine's
  dispatch table contains it; unknown names must not be silently skipped.
- Apply each variable to its own current value and assert the design is
  unchanged (a variable that mutates the model when it "does nothing" is a
  bug).
- Run the same optimizer twice with different settings on one instance and
  assert the results differ; assert the instance state is restored after a
  cancelled or failed run (no leaked merit function, no stale cache).
- Check the feasibility/constraint model against configurations the app
  itself ships (a cemented doublet, a mounted lens with a small clear
  aperture, a design at the edge of the variable box).
- Check the reported success flag against the physical penalty, not only the
  variable bounds.

### H. Environment, state, and metric contracts

- Compare a traced result against the same model computed by a second path
  (paraxial vs traced, analyzer vs environmental model, hand calculation) and
  assert they agree in sign and magnitude.
- Look for corrections stored in a field that the next update recomputes, and
  for state fields used as proxies for a different state.
- Reorder list arguments and assert the result does not change; compare
  sibling methods for consistent validation behaviour.
- For every override parameter, check that it reaches *all* consumers in the
  returned bundle, not just the first one.

### I. Shipped data, validators, and download paths

- Run the application's own validators over every shipped preset, seed row,
  mount, and catalogue entry; the data tables are usually exempt from the
  checks the code applies to user input.
- Compare seed/reference data with the reference object's own `to_dict()`.
- For every value the model can produce (including its special spellings
  such as `0` for an infinite radius), assert the validator accepts it.
- For download/update code, check what is verified besides the file size
  (digest, signature, magic bytes), whether a failed update is recoverable,
  and whether the temporary files and directories are cleaned up.
- For "atomic write" helpers, write the same file from two threads at once:
  a fixed temp name makes concurrent writers destroy each other.

## Phase 3 - Reproduce and grade

For each candidate, write `/tmp/opencode/repro_<slug>.py`:

```python
import os, sys
sys.path.insert(0, "/path/to/repo")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
# ... minimal setup ...
print("expected:", ...)
print("actual:  ", ...)
```

Rules for a good reproduction:

- Minimal: no GUI event loop unless the GUI is the bug.
- Deterministic: fixed seeds, fixed inputs.
- Self-contained: one file, runnable with the project interpreter.
- Output proves the claim in one or two lines (e.g. `save: True` then
  `load: None`; `C == F: True`; `changed: False`).

Grade severity:

| Grade | Meaning |
| --- | --- |
| high | Wrong optical results, data loss, crash on a normal path |
| medium | Wrong result in a narrower path, silent parameter no-op |
| low | Degenerate-input crash, cosmetic metric bug, missing warning |

Discard anything you cannot reproduce. Keep a note of near-misses so a later
reviewer does not repeat the dead end.

## Phase 4 - Deduplicate

```bash
gh issue list --state all --limit 300 --json number,title,state \
  --template '{{range .}}#{{.number}} [{{.state}}] {{.title}}{{"\n"}}{{end}}' \
  | grep -iE '<keyword1>|<keyword2>'
```

Also grep the issue bodies for the symbol/file name. If an open issue covers
the same root cause, add a comment with the new reproduction instead of opening
a duplicate. If a closed issue was fixed but the bug persists, open a new issue
that links it and states what regressed.

## Phase 5 - File the issue

Use the repository's existing labels. For OpenLens:

- `bug` - always, or the issue is invisible to the bug queue.
- Domain: `physics`, `gui`, `packaging`, `performance`, `data-loss`, `tech-debt`.
- Priority: `prio-high`, `prio-medium`, `prio-low`.
- IO findings have no `io` label; use `bug` + `prio-*` (+ `data-loss` if lossy).

```bash
scripts/file-issue.sh \
  --title "bug(physics): 2D tracer ignores wavelength for tilted elements" \
  --body /tmp/opencode/issues/tilt.md \
  --label bug --label physics --label prio-high
```

The script creates the issue, applies labels, and verifies them with
`gh issue view <n> --json labels`. Never create an unlabelled issue: an
unlabelled bug is invisible to `gh issue list --label bug`.

### Issue body template

```markdown
## Summary
One paragraph: what is wrong and where.

## Impact
Who hits it, when, and what they see. Quantify where possible
("same lens: 147.52 vs -1.213"; "save reports True, load returns None").

## Reproduction
```python
# minimal script, runnable as-is
```
Observed output:
```
...
```

## Root cause
`path/file.py:line` - the exact statement and why it fails.

## Expected behaviour
The contract that is violated.

## Suggested fix
One concrete direction, plus the regression test to add.
```

## Phase 6 - Report and commit

Produce a short table of filed issues: number, title, severity, subsystem.
State explicitly which subsystems were reviewed and which were not, and list
candidate findings that were rejected as non-issues (so the next reviewer does
not re-investigate them).

Commit only the review artifacts (the skill, any scripts/references). Do not
commit reproduction scripts under the repository; keep them in
`/tmp/opencode/`. Use:

```bash
git add .opencode/skills/code-review
git commit -m "docs(skill): add recurring code-review workflow"
```

## Parallelism

Reviewing a large repository is embarrassingly parallel. Launch one subagent
per subsystem with the same instructions: "reproduce with a script, report
file:line + output, do not file issues". Then do the filing centrally so labels,
titles, and deduplication stay consistent. Do not let two agents review the
same file.

## Definition of done

- Baseline recorded and green (or pre-existing failures documented).
- Every subsystem in scope reviewed.
- Every filed issue has a runnable reproduction and observed output.
- Every issue carries `bug` plus a priority and (where applicable) a domain label.
- Duplicates checked against open and closed issues.
- Review table posted and artifacts committed.
