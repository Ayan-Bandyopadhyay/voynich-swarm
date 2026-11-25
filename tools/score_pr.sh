#!/usr/bin/env bash
# Score one pull request on the hidden pages (run by .github/workflows/score.yml).
# Never executes code from the PR: only its experiment JSON is copied out with `git show`.
#   tools/score_pr.sh <pr number>
set -uo pipefail
PR=$1
if [ "$(gh pr view "$PR" --json labels --jq 'any(.labels[]; .name == "scored")')" = "true" ]; then echo "#$PR already scored"; exit 0; fi
git fetch -q origin "pull/$PR/head:pr-$PR" || exit 0
rm -rf _pr
if ! python3 tools/check_pr_shape.py origin/main --head "pr-$PR" --extract _pr > shape.txt 2>&1; then
  { echo "Not a single-experiment PR, so it is not scored automatically. Code PRs are reviewed by a person."; echo; echo '```'; head -20 shape.txt; echo '```'; } > comment.md
  gh pr comment "$PR" --body-file comment.md; gh pr edit "$PR" --add-label scored >/dev/null; exit 0
fi
mkdir -p secrets && printf '%s' "$HELDOUT_SEED_JSON" > secrets/heldout_seed.json
D=$(ls -d _pr/experiments/*/* | head -1)
URL=$(gh pr view "$PR" --json url --jq .url)
git pull -q --rebase origin main
timeout 1500 python3 -m vs score "$D" --pr "$URL" > verdict.txt 2>&1 || echo '{"verdict": "FAULT", "note": "the scorer failed or timed out; this says nothing about the submission"}' >> verdict.txt
rm -f secrets/heldout_seed.json
if grep -q '"verdict": "REFUSED"' verdict.txt; then H="Refused: nothing was scored and nothing goes on the record."
elif grep -q '"verdict": "FAULT"' verdict.txt; then H="FAULT: our scorer failed. Nothing is wrong with your submission; it will be retried."
else H="Scored on the hidden pages. The verdict is on the record."; fi
{ echo "$H"; echo; echo '```'; tail -40 verdict.txt; echo '```'; } > comment.md
gh pr comment "$PR" --body-file comment.md
if grep -q '"verdict": "FAULT"' verdict.txt; then exit 0; fi
gh pr edit "$PR" --add-label scored >/dev/null
if grep -q '"verdict": "REFUSED"' verdict.txt; then gh pr close "$PR" --comment "Refused before scoring. Fix it and open a new PR."; exit 0; fi
git add registry ledger pins results
git commit -q -m "record: scored #$PR" || true
for t in 1 2 3 4 5; do git pull -q --rebase origin main && git push -q origin HEAD:main && break; sleep 7; done
gh pr merge "$PR" --squash --delete-branch || true
