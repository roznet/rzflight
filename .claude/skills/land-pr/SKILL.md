---
name: land-pr
description: Land a PR the user has judged ready — check the review bot, run the Python and Swift suites locally on the PR head (there is no CI), merge with rebase, finish every remaining finding directly on main, tidy bookkeeping, and finish with a short landing summary and what /release will need. Invoke with the PR number. Never releases.
disable-model-invocation: true
---

# Land PR

The user runs this once they have **decided** the PR lands. Everything still open —
review findings, follow-ups, polish — gets finished with direct commits on `main` after
the merge, not by another PR round. Land it cleanly, finish it on main, and hand back a
summary they can absorb in a minute.

**Only these pause before the merge:**
1. The PR's own code **doesn't build or its tests fail** (Step 2).
2. Something that **can't be fixed after the merge**: a breaking Swift change (every
   Swift consumer tracks `main`, so merging *is* the Swift release — see
   `designs/consumers.md`) that the PR hasn't matched in or flagged to consumers; a close keyword that would wrongly
   close an outside reporter's or a consumer's issue; a version bump in the PR that is
   already published or tagged; a finding that would cause data loss or a security hole
   once released.

When you pause, **never run `/process-review` or anything else yourself.** Report what
you found and offer the options (fix on the branch, land anyway and fix on main, send it
back through `/process-review`), with your recommendation. The user decides.

Run locally on the Mac (Swift needs it). `gh` must run with the sandbox disabled.

## Inputs

- `<pr-number>` — required; if missing, use the PR for the current branch, else ask and
  stop.

## Step 1 — Pre-merge checks

1. **State:** open, not draft, `mergeStateStatus` not `DIRTY`.
   `gh pr view <n> --json state,isDraft,mergeStateStatus,headRefOid,baseRefName,body,commits,files`
2. **Review bot:** read **every** round's comment by `claude` whose first line contains
   "Code Review", not just the last. No review on the head commit → note it and carry on.
3. **Triage every open finding** across all rounds into "fix on main", "issue (needs
   design)" or "skip (why)". Pause only for the narrow cases above.
4. **Close keywords.** For each referenced issue, check where it lives and who filed it.
   This repo + filed by `roznet` → `Closes #N`. Outside reporter → `Addresses #N`.
   Consumer repo (`roznet/<repo>#N`) → no closing keyword. Check the PR body **and** every
   commit body, because GitHub acts on the commit:
   `git log origin/<base>..<head> --format=%B | grep -inE "close[sd]?|fixe?s?|resolve[sd]?"`.
   A stray keyword that would close the wrong issue → **pause**.
5. **Version.** If the PR touches `euro_aip/pyproject.toml` or `__init__.py`: the two must
   match, and the version must be neither on PyPI
   (`curl -s https://pypi.org/pypi/euro-aip/json | jq -r '.releases|keys[]'`) nor tagged
   (`git tag -l v<x.y.z>`). Already published → **pause**. Otherwise note it — `/release`
   will publish it.

## Step 2 — Verify the head locally (there is no CI)

1. Check the head out in a throwaway worktree:
   `git worktree add --detach .claude/worktrees/land-<n> <head-sha>`. Never switch the main
   checkout.
2. **Python:** from the worktree's `euro_aip/`, run the full suite with the main venv:
   `~/Developer/public/rzflight/euro_aip/venv/bin/pytest -q` (~10 s; it imports the
   worktree's code from there).
3. **Swift**, if the PR touches `Sources/`, `Tests/`, `Package.*` or a shared resource:
   `swift build && swift test` in the worktree (~30 s, longer on first build). Read the
   executed count; "0 tests" is not a pass.
4. **Pre-existing failures:** run any failing test on `origin/main` too. Fails there as
   well → baseline, note it, carry on. Fails only on the head → **pause** with the
   error excerpt and your recommendation (usually a fix pushed to the branch).
5. Remove the throwaway worktree when done.

## Step 3 — Merge

`gh pr merge <n> --rebase --delete-branch`. If the rebase doesn't apply, fall back to
`--merge` and say so. Confirm the linked issues closed (or deliberately did not).

## Step 4 — Finish it on main

- Sync a **clean** checkout of `main` to `origin/main`. If the main checkout has someone
  else's uncommitted changes, don't touch it — work from a clean worktree. Re-check the
  branch before committing.
- Apply **all** "fix on main" findings, plus small "Follow-ups noticed" from the brief.
  Anything that needs design thought → a **detailed issue** (root cause, call sites,
  acceptance criteria) for an implementation agent. A parity gap left by the PR → an issue
  naming the counterpart file, if the PR didn't already open one.
- Re-run the full Python suite, and Swift if you touched it, before pushing.
- One commit, `Follow-up to #<pr>: …`, specific paths only, attribution trailer. Push.

## Step 5 — Bookkeeping

- **Memory:** grep the memory dir for the issue/PR numbers; update notes that still call
  this work pending, or delete them if they're now only history.
- **Design docs (safety net):** check the PR updated the docs for what it changed. If not,
  or your on-main fixes changed documented behaviour, update the affected docs in the
  follow-up commit (locally `/sync-designs <doc path>`, never a full sync). New public API
  → INDEX `Key exports:`; a change in who uses what → `designs/consumers.md`.
- **Local worktree** for the PR branch: clean and merged → `git worktree remove`; dirty →
  leave it and say so.
- **Consumer issue** (`roznet/<repo>#N`): don't comment yet — the fix isn't usable until
  it's released. `/release` posts that.

## Step 6 — Landing summary

Final message, **≤ ~15 lines**, plain words — the PR's Owner's brief condensed and updated
with what actually happened:

```
## Landed #<pr> — <title>   (closes #N | for roznet/<repo>#N)

**What it does:** <one line>
**For consumers:** <who sees what, or "nothing until they call X">
**Fixed on main after merge:** <commit sha — what; or "none">
**Verified:** pytest <N passed, M pre-existing> · swift test <N passed | not touched>
**Release will need:** <bump patch|minor → 0.x.y (or "already bumped to 0.x.y"), pip and/or SPM tag, DB rebuild>
**Consumer follow-up:** <pin bumps / code changes in consumers, or "none">
**Left open:** <issues opened, deferred findings, decisions pending — or "none">
```

**Never release:** no version bump, build, `twine upload` or tag push here, and don't
start `/release`. Releasing is the user's separate, confirmed step.
