---
description: Watch a PR for the code-review bot's comment, then triage and act on it (fix blockers & push, or recommend merge + fix-on-main)
argument-hint: "[PR number] (default: PR for current branch)"
allowed-tools: Bash(gh:*), Bash(git:*), Bash(swift:*), Bash(./venv/bin/pytest:*), Bash(euro_aip/venv/bin/pytest:*), Read, Edit, Write, Grep, Glob
---

# Process bot review

Watch the target PR for the code-review bot's review, then triage and act on it.

Locally, `gh` must run with the sandbox disabled, otherwise it returns empty with exit 0.

## Target PR

- If `$ARGUMENTS` is a number, that is the PR.
- Otherwise resolve the PR for the current branch:
  `gh pr view --json number,headRefName,headRefOid,url`
- If there is no PR for the current branch, stop and tell me.

## The review bot

The reviewer is the GitHub user **`claude`**, driven by a **GitHub Action that fires automatically on every push** to the PR (`.github/workflows/claude-code-review.yml` → `.claude/commands/code-review.md`). It posts a single **top-level PR comment** (not inline threads) whose **first line is `## Code Review`**, grouping findings under `### Critical` / `### Important` / `### Minor`. A clean review posts a brief approval comment with no findings.

That shape is pinned in `.claude/commands/code-review.md` ("Output format"), but **match on the first line *containing* "Code Review", not on the exact `##` decoration**, so a future drift degrades into a cosmetic mismatch rather than a watch that silently never fires. Reviews posted before the format was pinned (PR #24 and earlier) have no heading at all; if a PR only has one of those, treat the latest `claude` comment after the head commit as the review and say so.

Because it is a top-level comment, it is **not** a GitHub "Review": `gh pr view --json reviews` and the inline `pulls/<n>/comments` endpoint are both always empty for this bot — an empty result there means nothing. The login also differs by API: `.author.login` is `claude` via `gh pr view --json comments` (used below), but `user.login` is `claude[bot]` via REST `issues/<n>/comments`.

**Cost model — every push = one full review round.** Two rules follow:
1. **Only push when there's a real blocker to fix.** If the findings are cosmetic-only, do *not* push — merge and fix on main, so you don't trigger (and wait on) another round.
2. **If you're pushing anyway, batch in everything worth doing.** Once a blocker forces a push, the round is already paid for — apply *every* fix you judge worth doing in that same push, cosmetic ones included.

Never manually re-trigger the bot; pushing is what triggers it.

## Step 1 — Wait for the review (watch)

"Ready" = a comment by `claude` whose **first line contains "Code Review"** that was created **after the latest commit on the PR branch** (so we don't act on a stale review from a previous round).

Capture the reference time — the head commit date:
`gh pr view <num> --json commits --jq '.commits[-1].committedDate'`

Then wait. **Prefer a GitHub MCP subscription if one is connected; otherwise fall back to `gh` polling.**

**Path A — GitHub MCP subscribe (preferred).** If a GitHub MCP server in this session exposes a PR-activity / comment subscription tool (look via ToolSearch for `subscribe`, `pr activity`, `watch`, `pull request comments`), subscribe to this PR and apply the same freshness filter when woken. Don't invent a server.

**Path B — `gh` polling (fallback).** Latest-wins query (`gh --jq` does not accept `--arg`, so pipe to `jq`):
```
gh pr view <num> --json comments | jq -r --arg t "<head-date>" \
  '[.comments[] | select(.author.login=="claude" and .createdAt > $t
    and ((.body | split("\n")[0]) | test("Code Review"; "i")))] | last | (.body // "NO_REVIEW_YET")'
```
Poll about every 60s as a background Bash loop that exits 0 once the comment is found, or via ScheduleWakeup — never a foreground `sleep` or a tight loop.

**Either path:** give up after ~20 min and report that no review appeared (the Action may not have run).

## Step 2 — Check for main divergence (before fixing)

`gh pr view <num> --json mergeStateStatus,baseRefName` and/or `git fetch origin main && git rev-list --left-right --count origin/main...HEAD`.

If `main` has moved ahead, **warn me and offer to rebase onto `main` first** (I prefer `--rebase`). **Do not auto-rebase** — wait for my go-ahead. Pay special attention if `main` carries a version bump the PR also makes: the rebase will conflict in `pyproject.toml` / `__init__.py` and the PR's version may need to move up.

## Step 3 — Triage

Read the full review body. Classify every finding. **Be strict about what counts as a blocker:** only correctness/logic/security/data-loss issues, clear design-intent violations, and **things that can't be fixed after a release** block a merge.

- **Blocker** — bug, logic error, wrong parser output, security issue, broken behaviour, real design-doc violation, an **unflagged breaking API change**, or a **version bump that is wrong** for the change (a published version can't be re-used). Anything under **Critical**, and **Important** findings that are genuinely about correctness or the release.
- **Cosmetic / non-blocking** — naming, comments, micro-optimisations, style, "consider…" with no behavioural impact. Most **Minor** findings. A Python↔Swift parity gap the PR already says it defers is usually here too (make sure an issue exists).
- **Unsure** — you can't tell whether it changes behaviour, or PR vs. main is a judgment call.

Before acting, post a short triage summary to me: one line per finding with bucket + reasoning.

## Step 4 — Act

**Blockers → fix and push to the PR branch.**
- Make the fixes. Reuse existing helpers; if the bot flagged a pattern, check whether it repeats in sibling parsers and on the other platform (Python ↔ Swift).
- Verify before pushing — there is **no CI test workflow** in this repo, so local runs are the only evidence:
  - Python: `cd euro_aip && ./venv/bin/pytest <targeted paths> -q` (never the repo-root `venv/`).
  - Swift (if `Sources/` or `Tests/` changed and you're on a Mac): `swift build` and `swift test --filter <TestClass>`. Not on a Mac → say "Swift written, not compiled".
  - A failure that also fails on `main` is pre-existing: note it, don't fix it in this push.
- Stage **specific paths** (never `git add -A`). Commit message references the finding; end the body with the `Co-Authored-By` trailer.
- Push. Then post a reply comment on the PR summarising what was fixed and what was deferred (audit trail for the next round). Its first line must **not** contain "Code Review".

**Cosmetic / non-blocking only → recommend merge + fix-on-main.**
- Do **not** push. Tell me they're non-blocking and recommend merging (`--rebase`), then a small direct-to-main commit.
- List the deferred items concretely; offer to (a) apply them on main after the merge, or (b) open a tracking issue.

**Unsure → ask me** with the specific finding: fix on the PR, or merge and fix on main?

**Mixed (blockers + cosmetic)** → you're pushing anyway, so batch in every cosmetic fix worth doing in the same push.

**Clean review (no findings)** → tell me it's ready and recommend merge (`--rebase`). State which tests you or the PR actually ran (there's no CI to point at). Don't auto-merge.

## Notes / guardrails

- **Never merge automatically**, and never build, `twine upload` or push release tags — releasing is my separate step.
- After pushing blocker fixes, the Action fires automatically — **do not re-trigger it.** Loop back to Step 1 for the next round, **capped at 2 rounds**; after that, summarise what's left and hand back.
- Issue-closing keywords: `Closes #N` only for issues filed by `roznet` in this repo. Outside reporters → `Addresses #N` (PR body **and** commit bodies). Consumer-repo issues (flyfun-weather, flyfun-apps, …) are referenced as `roznet/<repo>#N` without a closing keyword — the consumer issue closes when that repo picks up the release.
- Keep me in the loop with concise narration: what the bot found, your triage, what you pushed, what you deferred.
