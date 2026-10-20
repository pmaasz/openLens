---
name: Bug Fix Loop
description: Work through the GitHub issues labelled "bug" one at a time end to end - branch named after the issue, investigate and reproduce with a test, fix, verify, commit, open a PR, wait for green CI, squash-merge, then move to the next issue. Use when asked to fix the bug backlog, "work through the bugs", "fix issue N", or to sweep issues labelled bug.
---

# Bug Fix Loop

Resolve one labelled-`bug` issue at a time through the full lifecycle, then repeat
for the next one. Every issue gets its own branch, its own PR, and its own green
CI run.

## Repository facts (read these before starting)

| Fact | Value |
| --- | --- |
| Repo | `pmaasz/openLens` (`origin`) |
| Base branch | `master` (not `main`) |
| Branch name | `<issue-number>-<short-kebab-slug>`, e.g. `427-step-exporter-nameerror` |
| PR title | Conventional commit, e.g. `fix(io): resolve the StepExporter name typo` |
| Merge style | Squash (`--squash`); master history is linear |
| Local test runner | `python3` (system interpreter has PySide6 + matplotlib + numpy) |
| Local format/lint | `black` and `flake8` from `/home/philip/.local/bin` |
| Full CI | ~12 min per PR (Coverage is the long pole) |

Read `references/repo-facts.md` for the exact commands, known `gh` quirks in this
environment, and the pre-existing local test failures you must not attribute to
your change.

## Phase 0 - Pick the issue

```bash
scripts/next-issue.sh              # list open bugs, highest priority first
scripts/next-issue.sh 453          # show everything about one issue
```

Ordering is `prio-high` -> `prio-medium` -> `prio-low`, then oldest number
first. When the user names an issue explicitly, work on that one instead.

If the issue body lists several defects, fix all of them on that branch, or
split off follow-up issues - never leave one silently unfixed.

### Label every follow-up issue before moving on

`scripts/next-issue.sh` selects work with `gh issue list --label bug`. An
unlabelled issue is therefore **invisible to the loop**: it will never be picked
up, never appear in the triage list, and quietly sit in the tracker forever.
Four issues filed from the #438 and #470 fixes went unlabelled for exactly this
reason.

```bash
gh issue create --title "..." --body "..."          # labels: none by default
gh issue edit <n> --add-label bug,data-loss,prio-medium
```

Choose the labels from what the repo already has - check `gh label list` rather
than inventing new ones. The ones that carry meaning for triage:

- `bug` - required, or the issue is invisible to this loop.
- A domain label from the list (`physics`, `gui`, `packaging`, `performance`,
  `data-loss`, `tech-debt`) so the issue can be found again later.
- `prio-high` / `prio-medium` / `prio-low` - drives the ordering, so leaving it
  off is what the default sort falls back to. `data-loss` and `packaging`
  issues found mid-fix are normally `prio-medium`: real user impact, but
  usually a larger change than the issue it came from.

Verify the label took, and that the issue now appears in the queue:

```bash
gh issue view <n> --json labels
scripts/next-issue.sh | grep <n>

## Throughput: pipeline, do not serialise the wait

CI takes ~12 min per PR. Sitting idle through it wastes most of the run. Keep
exactly **one PR open** and **one fix in preparation**:

```text
fix N -> push N -> open PR N -> [ while CI(N) runs: fix N+1 on branch N+1 ]
       -> CI(N) green -> rebase N+1 onto new master -> push -> open PR N+1 -> ...
```

Because branch N+1 is still unpushed while CI(N) runs, rebasing it costs no CI
time at all. This gets the full benefit of parallelism without opening several
PRs at once.

Do **not** open several PRs before they are green: `on: push` triggers CI on
every branch, so a rebase after each merge would restart every pending PR's
checks and end up costing more than plain serial work.

## Phase 1 - Branch from a clean master

**Create the branch BEFORE the first edit, not before the first commit.** This
is not pedantry: three times in one session, work was edited on whatever branch
happened to be checked out and then lost - once to `gh pr merge --delete-branch`
removing the branch, and twice to a `git reset --hard` while tidying up master.
The untracked test file survived; the source change did not, and had to be
redone from scratch.

```bash
git checkout master
git pull --ff-only origin master
git checkout -b <number>-<short-kebab-slug>
```

Do that first, then read the code, then edit. If you have already edited
before branching, `git stash` the work, branch, and pop it.

Derive the slug from the issue title: 3-6 lowercase kebab-case words that
summarise the work, not the ticket title verbatim. Keep it short.

If the working tree is dirty with changes you did not make, stop and ask before
discarding anything.

## Phase 2 - Reproduce first, in a test

Never fix a bug you cannot demonstrate. Before touching `openlens/`:

1. `scripts/next-issue.sh <n>` and read the issue body; the **Where:** line names
   the files and lines involved.
2. Read the offending code and the tests that already cover it
   (`ls tests/`, `grep` for the symbol).
3. Write a test that fails on current `master` for the reason the issue
   describes. Put it in the existing matching test module, following its
   conventions.

```bash
python3 -m unittest tests.test_<module>.<Class>.test_<what>
```

Confirm it fails, and that the failure message is the bug - not a typo, not an
import error. This is the evidence the fix is real.

## Phase 3 - Fix

- Make the smallest change that fixes the root cause.
- Respect `AGENTS.md`: constants from `openlens/constants.py`, `logger.*` instead of
  `print()`, Google-style docstrings, type hints, 100-char lines, optional
  imports guarded with a `*_AVAILABLE` flag.
- Keep the fix scoped to the issue. Unrelated cleanups belong in their own branch.
- For physics/optics bugs, state the formula or limit you are enforcing in the
  commit body, and sanity-check against a known value (thin lens, paraxial
  limit, a reference glass) rather than only the new assertion.

## Phase 4 - Verify locally

```bash
black --line-length=100 --exclude 'openlens/__main__.py' openlens/ tests/ --check
flake8 openlens/ tests/ --max-line-length=100 --ignore=E203,W503
QT_QPA_PLATFORM=offscreen OPENLENS_SKIP_SLOW=1 python3 -m unittest discover -s tests -t .
```

`black` is the only blocking lint job in CI. The six
`tests/gui_flows/test_*` loader errors are a local artifact (pytest is not
installed here) - compare against the baseline in `references/repo-facts.md`
rather than expecting zero.

Re-run your new test to confirm it now passes, and run the tests for every
module you touched.

## Phase 5 - Commit

One logical commit, conventional format, ticket in the subject:

```
fix(io): resolve the StepExporter name typo

StepExporter.__init__ stored the exporter as self.step_exporter while every
call site read self.exporter, so File > Export to STEP raised NameError on a
non-empty selection. Use one attribute name.

Closes #427
```

Then push:

```bash
git push -u origin <branch>
```

A branch is pushed exactly once. If it must be rebased afterwards (see Phase
8), that is the one legitimate reason to force-push - use `--force-with-lease`,
never plain `--force`.

## Phase 6 - Open the PR

```bash
scripts/pr-body.sh <number> "<title>"   # generates the body from the issue
gh pr create --base master --head <branch> --title "<title>" --body-file /tmp/pr-body.md
```

The body must contain `Closes #<number>` so the issue closes on merge. Use
`--json` with `gh issue view` (see quirks) and never hand-wave the test list.

## Phase 7 - Wait for green CI

```bash
scripts/watch-ci.sh            # waits, then prints a verdict
```

This is the gate. Do not merge while any check is pending or failing.

If a check fails, read the log, fix it on the same branch, and re-run:

```bash
gh run view <run-id> --log-failed
```

Pushing a new commit restarts the checks. Never merge red to "unblock" the
queue - fix it.

## Phase 8 - Merge, rebase, clean up

Only when `scripts/watch-ci.sh` reports success:

```bash
gh pr merge <pr-number> --squash --delete-branch
git checkout master
git pull --ff-only origin master
git branch -d <branch>
```

**`gh pr merge --delete-branch` deletes the local branch too.** If that branch
carries a commit that is not in the PR - because work was committed to the
wrong branch - that commit goes with it. Recover it from the reflog
(`git reflog`, then `git branch <name> <hash>`) before it is garbage
collected. This is the other reason Phase 1 insists on branching first.

Then **rebase the in-preparation branch for the next issue onto the new
master** - it was cut from the pre-merge commit and may now be stale or
conflicting:

```bash
git rebase master          # on the prepared next-issue branch
```

Re-run Phase 4 on it after rebasing, because master just gained another fix.

Note that rebasing a branch with an open PR restarts its CI. That is the cost
of the ordering, and it is why only one PR is open at a time.

`Closes #<n>` closes the issue automatically. Verify:

```bash
gh issue view <number> --json state
```

## Phase 9 - Next issue

Report the merged PR URL, then return to Phase 0 for the next open `bug`.
Skip issues that turned out to be duplicates or already fixed - comment the
finding on the issue and close it rather than burning a PR on it.

## Safety rules

1. Never merge with red or pending CI.
2. Force-push only as `--force-with-lease`, and only right after a deliberate
   rebase of a branch you own.
3. Never commit `openlens.db`, `lenses.db`, `data/`, `specs/`, `dist/`,
   `.venv/` (all gitignored - verify with `git status` before committing).
4. Never close an issue without a merged PR or an explicit user instruction.
5. Keep at most one PR open at a time.
6. Stop and ask when the fix would require a behavioural redesign, a schema
   migration, or a change to a public API the issue does not ask for.
