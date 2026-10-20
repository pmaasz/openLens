#!/usr/bin/env bash
# watch-ci.sh - block until every PR check settles, then print a verdict.
#
#   scripts/watch-ci.sh [pr-number]     default: the PR for the current branch
#
# Exit status: 0 only when every check has passed.
# Never merge on a non-zero status - fix the branch and push again.
#
# Note on gh's exit codes: `gh pr checks` returns 0 for all-passed, 8 for
# still-pending, and 1 for a failure - but it ALSO returns 1 when it cannot
# reach api.github.com at all. Treating that as a red build makes the loop
# abandon a perfectly healthy PR on a network blip, so transport errors are
# detected and retried separately from a genuine failing check.

set -uo pipefail

RETRY_SECONDS=${RETRY_SECONDS:-45}
MAX_TRANSPORT_ERRORS=${MAX_TRANSPORT_ERRORS:-20}

pr="${1:-}"
if [[ -z "$pr" ]]; then
  pr=$(gh pr view --json number --jq .number 2>/dev/null)
  if [[ -z "$pr" ]]; then
    echo "no open PR found for the current branch" >&2
    exit 2
  fi
fi

echo "waiting for CI on PR #${pr} (this takes ~12 min) ..."

is_transport_error() {
  # Anything matched here means "we could not ask", not "CI said no".
  # Reporting an unreachable API as a CI failure points the agent at the
  # branch under review when the branch is fine - it invites a re-run of a
  # suite that already passes, and hunting a bug that does not exist.
  # A TLS handshake timeout was doing exactly that: it fell through to the
  # verdict branch on PR #520 while every job was still pending.
  grep -qiE "error connecting|could not resolve (to )?host|no such host|lookup .*(: no such host)?$|connection (refused|reset|timed out)|i/o timeout|TLS handshake timeout|handshake timeout|net/http:|502 Bad Gateway|503 Service Unavailable" <<<"$1"
}

transport_errors=0
while true; do
  out=$(gh pr checks "$pr" 2>&1)
  code=$?

  if is_transport_error "$out"; then
    transport_errors=$((transport_errors + 1))
    if (( transport_errors >= MAX_TRANSPORT_ERRORS )); then
      echo "VERDICT: could not reach the GitHub API after ${transport_errors} attempts."
      echo "This is a network problem, not a CI result - check the PR by hand."
      exit 2
    fi
    echo "  (gh could not reach the API, retrying in ${RETRY_SECONDS}s ...)"
    sleep "$RETRY_SECONDS"
    continue
  fi

  case "$code" in
    0)
      printf '%s\n' "$out"
      echo
      echo "VERDICT: all checks GREEN"
      exit 0
      ;;
    8)
      # still pending - poll again
      sleep "$RETRY_SECONDS"
      ;;
    *)
      printf '%s\n' "$out"
      echo
      echo "VERDICT: CI NOT GREEN - fix and push again, do not merge"
      echo
      echo "--- failed job logs ---"
      for run in $(gh run list --branch "$(git rev-parse --abbrev-ref HEAD)" --limit 1 \
                     --json databaseId --jq '.[0].databaseId'); do
        gh run view "$run" --log-failed 2>/dev/null | tail -80
      done
      exit 1
      ;;
  esac
done
