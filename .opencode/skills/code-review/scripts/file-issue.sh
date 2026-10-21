#!/usr/bin/env bash
# Create a labelled GitHub issue and verify the labels took.
#
# Usage:
#   scripts/file-issue.sh --title "bug: ..." --body /path/to/body.md \
#       --label bug --label physics --label prio-high [--repo owner/name]
#
# Exits non-zero if the issue cannot be created or a label is unknown.
set -euo pipefail

TITLE=""
BODY=""
REPO_ARGS=()
LABELS=()

usage() {
    sed -n '2,10p' "$0"
    exit "${1:-2}"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --title) TITLE="$2"; shift 2 ;;
        --body)  BODY="$2";  shift 2 ;;
        --label) LABELS+=("$2"); shift 2 ;;
        --repo)  REPO_ARGS=(--repo "$2"); shift 2 ;;
        -h|--help) usage 0 ;;
        *) echo "unknown argument: $1" >&2; usage ;;
    esac
done

[[ -n "$TITLE" ]] || { echo "error: --title is required" >&2; usage; }
[[ -n "$BODY" && -f "$BODY" ]] || { echo "error: --body must be an existing file" >&2; usage; }

# Reject labels the repository does not have: gh issue create fails late and
# leaves a confusing error otherwise.
if [[ ${#LABELS[@]} -gt 0 ]]; then
    AVAILABLE="$(gh label list --limit 200 "${REPO_ARGS[@]}" --json name -q '.[].name')"
    for label in "${LABELS[@]}"; do
        if ! grep -qxF "$label" <<<"$AVAILABLE"; then
            echo "error: label '$label' does not exist in this repository" >&2
            echo "available labels:" >&2
            echo "$AVAILABLE" | sed 's/^/  /' >&2
            exit 1
        fi
    done
fi

ARGS=(issue create "${REPO_ARGS[@]}" --title "$TITLE" --body-file "$BODY")
for label in "${LABELS[@]}"; do
    ARGS+=(--label "$label")
done

URL="$(gh "${ARGS[@]}")"
NUMBER="$(basename "$URL")"

# Verify instead of trusting the create output.
gh issue view "$NUMBER" "${REPO_ARGS[@]}" --json number,title,url,labels \
    --template '#{{.number}} {{.title}}{{"\n"}}labels: {{range .labels}}{{.name}} {{end}}{{"\n"}}{{.url}}{{"\n"}}'

echo "created: $URL"
