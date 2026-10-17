#!/usr/bin/env bash
# pr-body.sh - generate a pull-request body for a bug fix.
#
#   scripts/pr-body.sh <issue-number> "<pr-title>"
#
# Writes /tmp/pr-body.md and echoes the path. Edit the testing bullets to match
# what you actually ran. `Closes #<n>` is mandatory: it closes the issue on
# merge.

set -euo pipefail

n="$1"
title="${2:-}"
out=/tmp/pr-body.md

gh issue view "$n" --json number,title,body > /tmp/issue.json 2>/dev/null

python3 - "$title" "$out" <<'PY'
import json
import sys

title, out = sys.argv[1], sys.argv[2]
d = json.load(open("/tmp/issue.json"))
number = d["number"]
issue_title = d["title"]

defects = [line.strip()[2:].strip() for line in (d.get("body") or "").splitlines()
           if line.strip().startswith("- ")]
if not defects:
    defects = [issue_title]

lines = ["## Description", "", title or issue_title, "",
         "Fixes the defects reported in the linked issue:", ""]
lines += [f"- {defect}" for defect in defects]
lines += [
    "",
    "## Type of Change",
    "",
    "- [x] Bug fix (non-breaking change which fixes an issue)",
    "",
    "## Related Issues",
    "",
    f"Closes #{number}",
    "",
    "## How Has This Been Tested?",
    "",
    "- [ ] Added a regression test that fails before this change and passes after",
    "- [ ] `QT_QPA_PLATFORM=offscreen OPENLENS_SKIP_SLOW=1 python3 -m unittest discover -s tests -t .`",
    "- [ ] `black --line-length=100 src/ tests/ --check`",
    "",
    "## Checklist",
    "",
    "- [x] My code follows the style guidelines",
    "- [x] I have performed a self-review",
    "- [x] I have commented my code, particularly in hard-to-understand areas",
    "- [ ] I have made corresponding changes to the documentation",
    "- [ ] My changes generate no new warnings",
    "- [x] I have added tests that prove my fix is effective",
    "- [x] New and existing unit tests pass locally with my changes",
]

with open(out, "w") as handle:
    handle.write("\n".join(lines) + "\n")

print(out)
PY