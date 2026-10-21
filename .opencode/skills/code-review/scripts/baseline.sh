#!/usr/bin/env bash
# Record a reproducible review baseline: commit, tree state, tests, lint.
#
# Usage:
#   scripts/baseline.sh [log-path]
#
# Default log: /tmp/opencode/review-baseline.log
# Exits with the test-suite status (0 = green) so callers can gate on it.
set -uo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
LOG="${1:-/tmp/opencode/review-baseline.log}"
mkdir -p "$(dirname "$LOG")"

cd "$REPO_ROOT"

if [[ -n "${PYTHON:-}" ]]; then
    : # caller override
elif [[ -x ".venv/bin/python" ]] && \
     .venv/bin/python -c "import PySide6, numpy" >/dev/null 2>&1; then
    PYTHON=".venv/bin/python"
else
    # A .venv without the GUI deps produces dozens of spurious import errors;
    # prefer the interpreter that can actually run the suite.
    PYTHON="python3"
fi

{
    echo "=== Review baseline ==="
    echo "date:   $(date -Iseconds)"
    echo "repo:   $REPO_ROOT"
    echo "commit: $(git rev-parse HEAD 2>/dev/null || echo 'not a git repo')"
    echo "branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'n/a')"
    echo "python: $PYTHON ($("$PYTHON" --version 2>&1))"
    echo
    echo "=== Working tree ==="
    git status --short 2>/dev/null || true
    echo
    echo "=== Tests (OPENLENS_SKIP_SLOW=1) ==="
} | tee "$LOG"

QT_QPA_PLATFORM=offscreen OPENLENS_SKIP_SLOW=1 \
    "$PYTHON" -m unittest discover -s tests -t . 2>&1 | tee -a "$LOG"
TEST_RC=${PIPESTATUS[0]}

{
    echo
    echo "test_rc: $TEST_RC"
    echo
    echo "=== Lint ==="
} | tee -a "$LOG"

if [[ -x ".venv/bin/ruff" ]]; then
    .venv/bin/ruff check openlens tests 2>&1 | tee -a "$LOG"
    LINT_RC=${PIPESTATUS[0]}
elif command -v ruff >/dev/null 2>&1; then
    ruff check openlens tests 2>&1 | tee -a "$LOG"
    LINT_RC=${PIPESTATUS[0]}
elif command -v flake8 >/dev/null 2>&1; then
    flake8 openlens tests --max-line-length=100 --ignore=E203,W503 2>&1 | tee -a "$LOG"
    LINT_RC=${PIPESTATUS[0]}
else
    echo "(no ruff or flake8 on PATH; skipped)" | tee -a "$LOG"
    LINT_RC=0
fi

echo "lint_rc: $LINT_RC" | tee -a "$LOG"
echo "log: $LOG"
exit "$TEST_RC"
