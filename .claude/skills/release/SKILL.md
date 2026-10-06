---
name: release
description: Release euro_aip to PyPI — work out what changed since the last v-tag, propose the version bump, run both test suites, bump both version files, build, and (after explicit confirmation) twine upload and tag; optionally mark the Swift side with a 1.x.y tag; then list which consumers (flyfun-weather, flyfun-apps, flyfun-forms, …) should move their pin and tell consumer issues the fix is out. Invoke with an optional bump (patch / minor) or explicit version.
disable-model-invocation: true
---

# Release

rzflight's version of a deploy. Publishing to PyPI is **irreversible** (a version number
can never be re-used), so this skill does all the preparation, then shows a plan and
**waits for an explicit go** before `twine upload` and pushing tags. Procedure background:
`designs/releasing.md`; who consumes what: `designs/consumers.md`.

Run locally, on a clean `main`. `gh` and `curl` must run with the sandbox disabled.

## Inputs

- `[patch | minor | <x.y.z>]` — optional. Without it, propose one in Step 2.

## Step 1 — Where are we

1. `git fetch --tags origin`; must be on `main`, clean, and equal to `origin/main`. Not
   clean or behind → stop and say so (other sessions share this checkout).
2. Versions:
   - files: `euro_aip/pyproject.toml` `version` and `euro_aip/euro_aip/__init__.py`
     `__version__` — if they differ, stop: fix that first.
   - PyPI: `curl -s https://pypi.org/pypi/euro-aip/json | jq -r .info.version`
   - last pip tag: `git describe --tags --match 'v*' --abbrev=0`
   - last Swift tag: `git tag -l '[0-9]*' --sort=-v:refname | head -1`
3. Decide the state:
   - files == PyPI == last tag → nothing pending; a bump is needed.
   - files > PyPI, no tag for it → **a PR already bumped it** (common): release that
     version as is unless the changes call for a bigger bump.
   - files == PyPI but no tag, or a tag but not on PyPI → a half-finished earlier release:
     report it and finish just the missing step, with confirmation.

## Step 2 — What's in it

1. Python changes since the last pip tag:
   `git log --format='%h %s' v<last>..HEAD -- euro_aip/euro_aip euro_aip/pyproject.toml`
   (ignore commits touching only tests or designs). Nothing → no pip release needed; say so
   and skip to Step 6 for Swift.
2. Swift changes since the last Swift tag: `git log --format='%h %s' <last-swift>..HEAD --
   Sources Package.swift`. These are **already live** for consumers (they track `main`); a
   tag is only a marker.
3. Classify each Python commit: `feat` / additive API → minor; `fix` → patch; anything
   breaking (signature, removed name, parser output change, DB schema) → minor, and list
   it under **Breaking** in the plan. Check merged PR bodies for their "Release:" brief line:
   `gh pr list --state merged --search "merged:>=<last-tag-date>" --json number,title,body`.
4. Consumer issues addressed: `roznet/<repo>#N` references in those commit messages and PR
   bodies.
5. Proposed version = the highest bump any change needs (or the input).

## Step 3 — Verify

Both suites, on the exact commit to be released:

- `cd euro_aip && ./venv/bin/pytest -q` — full suite (~10 s). If an import of a declared
  dependency fails, refresh the venv first: `./venv/bin/pip install -e .`
- `swift build && swift test` from the repo root (~30 s).
- Any failure: is it on the previous release tag too
  (`git worktree add --detach .claude/worktrees/rel-base v<last>` and re-run)? Pre-existing
  → list it in the plan. New since the last release → **stop**: don't release over a
  regression.

## Step 4 — Plan, and wait for go

Show and stop:

```
## Release plan — euro_aip <old> → <new>

**Changes:** <one line each: sha subject>
**Breaking:** <list, or "none">
**Tests:** pytest <N passed, M pre-existing (names)> · swift test <N passed>
**Steps:** bump commit (if needed) → push → build → twine check → twine upload → tag v<new> → push tag
**Swift marker tag:** <propose 1.x.y for N Swift commits since <last>, or "none">
**Consumers after release:** <repo: pin >=old → suggest >=new, because …>
```

Proceed only on an explicit yes. Partial yes (e.g. "no Swift tag") → do only that.

## Step 5 — Publish (only after go)

1. **Bump** (if the files aren't already at `<new>`): edit both files, commit only them —
   `chore(release): bump euro_aip to <new>` with the attribution trailer — and push `main`.
2. **Build** from `euro_aip/`: `rm -rf dist build && ./venv/bin/python -m build`, then
   `./venv/bin/twine check dist/*`. The artefacts must be named `euro_aip-<new>`.
3. **Upload:** `./venv/bin/twine upload dist/*` (credentials from `~/.pypirc`). If it
   fails, stop and report; don't tag a version that isn't on PyPI.
4. Confirm: `curl -s https://pypi.org/pypi/euro-aip/<new>/json | jq -r .info.version`.
5. **Tag** the bump commit: `git tag v<new> <sha> && git push origin v<new>`.

## Step 6 — Swift marker tag (only if agreed)

`git tag <1.x.y> <sha> && git push origin <1.x.y>`, bare semver, no `v`. Minor for new
API, patch for fixes. Remember no consumer resolves by tag today, so this is bookkeeping.

## Step 7 — Consumers

1. **Pins.** For each consumer in `designs/consumers.md`, read its current pin:
   `flyfun-weather/main/pyproject.toml`, `flyfun-apps/main/requirements.txt`,
   `flyfun-forms/main/pyproject.toml` (grep `euro-aip`). Recommend a bump only where the
   release contains something that consumer uses or asked for; otherwise leave the pin.
2. **Don't edit consumer repos from here** without a yes. On a yes, follow that repo's own
   way of working (its CLAUDE.md / skills, usually a small PR); never touch a consumer
   checkout that has someone else's uncommitted changes.
3. **Consumer issues** from Step 2: on a yes, comment once on each
   (`gh issue comment N -R roznet/<repo>`): "Released in euro-aip <new> (<sha>): <what it
   provides / how to use it>". Don't close them — the consumer closes its issue once it
   has adopted the release.

## Step 8 — Summary

```
## Released euro_aip <new>

**PyPI:** <url> · **tag:** v<new> (<sha>) · **Swift marker:** <1.x.y | none>
**In it:** <2–4 lines, plain words; breaking first>
**Tests:** <counts, pre-existing failures named>
**Consumers:** <repo: pin bumped / suggested / not needed>
**Left open:** <half-done steps, failures, follow-ups — or "none">
```

Never `--force` a tag, delete a tag, or re-upload. If something went wrong after the
upload, report it and propose a new patch release instead.
