#!/usr/bin/env bash
# next-issue.sh - list open `bug` issues in triage order, or dump one issue.
#
#   scripts/next-issue.sh          list open bugs: prio-high, then -medium, then -low
#   scripts/next-issue.sh 453      full detail for one issue + a branch-name candidate
#
# Uses --json on every `gh` call: plain `gh issue view` dies on the retired
# GraphQL projectCards field in this environment.

set -uo pipefail

slug() { # title -> candidate branch slug (lowercase kebab, up to 6 words)
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -e 's/`//g' -e "s/'//g" -e 's/"/ /g' \
    | tr -cs 'a-z0-9' '\n' \
    | grep -Ev '^(the|a|an|is|are|to|of|in|on|and|or|not|no|with|for|when|does|do|it|its|from|by|as|at|be|was|that|this|than|then|if|but|can|will|should|would|could|has|have|had|also|only|too|very|just|so|up|out|into|over|after|before|their|them|they|there|here|what|which|while|where|how|all|any|each|other|more|most|some|such)$' \
    | grep -v '^$' \
    | head -6 \
    | paste -sd-
}

if [[ $# -ge 1 ]]; then
  n="$1"
  # mktemp, not a fixed path: two invocations running at once (the loop
  # prepares the next issue while a PR's CI runs) would otherwise
  # interleave writes into the same file and corrupt both reads.
  issue_file=$(mktemp)
  trap 'rm -f "$issue_file"' EXIT
  gh issue view "$n" --json number,title,state,url,labels,body > "$issue_file" 2>/dev/null
  title=$(gh issue view "$n" --json title --jq .title 2>/dev/null)

  ISSUE_FILE="$issue_file" python3 - <<'PY'
import json
import os

d = json.load(open(os.environ["ISSUE_FILE"]))
labels = [label["name"] for label in d.get("labels", [])]
print(f"=== issue #{d['number']} ===")
print(f"title : {d['title']}")
print(f"state : {d['state']}")
print(f"url   : {d['url']}")
print(f"labels: {', '.join(labels)}")
print("---")
print(d.get("body") or "(no body)")
PY

  echo
  echo "=== branch ==="
  echo "${n}-$(slug "$title")"
  exit 0
fi

bugs_file=$(mktemp)
trap 'rm -f "$bugs_file"' EXIT
gh issue list --label bug --state open --limit 100 --json number,title,labels > "$bugs_file" 2>/dev/null

BUGS_FILE="$bugs_file" python3 - <<'PY'
import json
import os

RANK = {"prio-high": 0, "prio-medium": 1, "prio-low": 2}
issues = json.load(open(os.environ["BUGS_FILE"]))


def rank(labels):
    for name in labels:
        if name in RANK:
            return RANK[name]
    return 3


def names(issue):
    return [label["name"] for label in issue["labels"]]


print("=== open issues labelled bug ===")
for issue in sorted(issues, key=lambda i: (rank(names(i)), i["number"])):
    extra = [name for name in names(issue) if name != "bug"]
    title = issue["title"]
    if len(title) > 60:
        title = title[:57] + "..."
    print(f"#{issue['number']:<5} [{rank(names(issue))}] {' '.join(extra):<30} {title}")

print(f"\n{len(issues)} open bug issue(s)")
PY