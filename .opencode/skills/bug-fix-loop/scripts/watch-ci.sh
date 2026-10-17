#!/usr/bin/env bash
# watch-ci.sh - block until every PR check settles, then print a verdict.
#
#   scripts/watch-ci.sh [pr-number]     default: the PR for the current branch
#
# Exit status: 0 only when every check has passed.
# Never merge on a non-zero status - fix the branch and push again.

set -uo pipefail

pr="${1:-}"
if [[ -z "$pr" ]]; then
  pr=$(gh pr view --json number --jq .number 2>/dev/null)
  if [[ -z "$pr" ]]; then
    echo "no open PR found for the current branch" >&2
    exit 2
  fi
fi

echo "waiting for CI on PR #${pr} (this takes ~12 min) ..."

result=0
while true; do
  # `gh pr checks` exits 8 while checks are pending, non-zero on failure.
  out=$(gh pr checks "$pr" 2>&1)
  code=$?
  case "$code" in
    0)
      printf '%s\n' "$out"
      echo
      echo "VERDICT: all checks GREEN"
      exit 0
      ;;
    8)
      # still pending - poll again
      sleep 45
      ;;
    *)
      printf '%s\n' "$out"
      echo
      echo "VERDICT: CI NOT GREEN - fix and push again, do not merge"
      result=1
      break
      ;;
  esac
done

if [[ "$result" -ne 0 ]]; then
  echo
  echo "--- failed job logs ---"
  for run in $(gh run list --branch "$(git rev-parse --abbrev-ref HEAD)" --limit 1 \
                 --json databaseId --jq '.[0].databaseId'); do
    gh run view "$run" --log-failed 2>/dev/null | tail -80
  done
fi

exit "$result"