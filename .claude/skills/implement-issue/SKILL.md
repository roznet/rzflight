---
name: implement-issue
description: Implement a GitHub issue end-to-end — rzflight's own (#N) or a consumer's (roznet/flyfun-weather#N) — read the thread, design docs and the consumer's call site, branch, implement in Python and/or Swift, run both test suites where possible, open a PR, and finish with a short owner's brief (API impact, which consumers are affected, what the release will need, how we know it works) plus a "pick up on a Mac" checklist for what couldn't be built here. Invoke with the issue number or reference.
disable-model-invocation: true
---

# Implement issue

The user owns this library and its consumers (`designs/consumers.md`) but doesn't
review code line by line. The deliverable is **two things**: a PR that works, and a
brief that lets them understand and own what went in within a couple of minutes —
including what it means for each consumer and for the next release. This often runs
unattended (cloud / background); they'll read the brief later, possibly on a phone.

## Inputs

- `<issue>` — required: `N` (this repo), `roznet/<repo>#N`, or an issue URL. If missing,
  ask and stop.

## Step 0 — Know where you are

Detect, don't assume, and remember the answers for the brief:

- **Cloud or local Mac?** Cloud if `CLAUDE_CODE_REMOTE=true`, or the checkout is not
  `~/Developer/public/rzflight` (or a worktree of it). Cloud is already an isolated,
  throwaway checkout: no worktree, no consumer checkouts on disk.
- **Attended or unattended?** Background/cloud, or the user said they're away →
  **unattended**: never stop to ask; take the most conservative, reversible option and
  record it under "Decisions I made for you". Attended → ask only for decisions that are
  genuinely theirs.
- **Toolchain:**
  - Python: locally `euro_aip/venv/bin/python` (never the repo-root `venv/`). In the
    cloud, `pip install -e "euro_aip[dev]"` into whatever Python ≥ 3.12 the sandbox has.
    If an import of a declared dependency fails locally, the venv is stale:
    `cd euro_aip && ./venv/bin/pip install -e .`
  - Swift: `command -v swift` **and** macOS. In the cloud there's no Swift build
    (CoreLocation/MapKit/UIKit) — write the Swift anyway, carefully, and hand
    build/test to the Mac checklist.
  - `gh` works (locally it must run with the sandbox disabled, else it returns empty with
    exit 0).

## Step 1 — Understand before touching code

1. `gh issue view <n> [-R roznet/<repo>] --comments` — read the **whole thread**; later
   comments supersede the body. Follow linked issues/PRs the plan depends on.
2. **Consumer issue?** Find what the consumer actually needs: locally, read its call site
   in `~/Developer/public/<repo>/main/` (or `<repo>/`); in the cloud, use what the issue
   quotes. The library should solve the general problem, not encode one caller's quirk.
3. Check it isn't already done: `git log --oneline --all --grep "#<n>"` and
   `gh pr list --state all --search "<n>"`. If work exists, build on it.
4. Design docs first (`designs/INDEX.md` → the module's doc). If public API, parser
   output or the DB schema may change, read `designs/consumers.md` and grep the consumer
   checkouts for callers.
5. **Classify the change** — this sets how careful the brief must be:
   - **Internal** — refactor, private code, tests. No consumer-visible change.
   - **Public API — additive** — new name, new optional argument, new field.
   - **Public API — breaking** — changed signature or return shape, removed/renamed name,
     a new required argument.
   - **Parser behaviour** — same input now gives different output (METAR/TAF, NOTAM, FPL,
     AIP field interpretation). Breaking in effect even with an unchanged signature.
   - **Data & sources** — a scraper/API source, AIRAC handling, or the `airports.db`
     schema / `DatabaseStorage`. Affects flyfun-apps' build and every DB reader.
   Swift changes are more exposed than Python ones: every Swift consumer tracks
   `main`, so a merged Swift change reaches the apps with no version gate.
   Not a closed list: if part of the change carries a risk these don't name (network
   cost, credentials, security), add your own label rather than folding it into
   "internal". Most issues are a mix; estimate the split.
6. **Breaking change or a real design choice, attended:** before implementing, give a
   5-line plan (what changes, the 1–3 choices that are theirs, your recommendation) and
   wait. Unattended: implement the conservative option (additive over breaking, old
   behaviour as the default) and flag it prominently in the brief.

## Step 2 — Branch

- **Cloud:** no worktree. Use the session's working branch if there is one, else
  `git checkout -b issue-<n>-<slug> origin/main`.
- **Local, already on a branch/worktree for this issue:** use it.
- **Local, on `main`:** don't implement on `main` — other sessions share the checkout.
  Create a worktree under `.claude/worktrees/` (the `EnterWorktree` tool, or
  `git worktree add -b issue-<n>-<slug> .claude/worktrees/issue-<n>-<slug> origin/main`).
  - Python: reuse the main checkout's venv. Run it **from the worktree's `euro_aip/`**:
    `~/Developer/public/rzflight/euro_aip/venv/bin/pytest …`. From there it imports the
    worktree's code, not main's; confirm once with
    `…/venv/bin/python -c "import euro_aip; print(euro_aip.__file__)"`.
  - Swift: `swift build` in the worktree uses its own `.build/`; the first build is slower.
- For a consumer issue, name the branch `<repo>-<n>-<slug>`.
- Re-check HEAD and branch before every commit.

## Step 3 — Implement

- Follow `.claude/CLAUDE.md`. Search before duplicating; update **all** callers on a
  signature change, in both languages.
- **Prefer additive.** New behaviour behind a new argument or method, old behaviour as
  the default, unless the issue explicitly asks to change the default.
- **Parity.** If the logic exists on the other side (see `.claude/CLAUDE.md`), change both,
  or leave the other and say so in the brief with the counterpart file and an issue. Shared
  config files change in every copy.
- **Tests** next to the change. No network: mock HTTP. Include at least one real-shaped
  sample (a real METAR/NOTAM/AIP snippet, redacted if needed), not only strings written to
  fit the code. Test data uses fictional registrations and names.
- **Don't bump the version.** Concurrent PRs would each claim the same next version. Put
  the bump you recommend in the brief; `/release` applies it.
- Keep scope to the issue. Things you notice go under "Follow-ups" in the brief.

### Design docs, in the same PR

Once the code is settled, update the design docs **for the code you touched** (via
`designs/INDEX.md`): architecture, key exports, gotchas and above all **choices and their
rationale**. New public API → its doc and the INDEX `Key exports:` line. A change in who
uses what → `designs/consumers.md`. Keep docs notes for a future agent, not a changelog.
Locally, `/sync-designs <doc path>` does this well; never a full sync. No doc needed
updating? Say so in the brief.

## Step 4 — Verify

There is **no CI test workflow** in this repo, so your runs are the only evidence.
Record real outcomes (counts, not "looks good").

- **Python:** the full suite is fast (~10 s): `cd euro_aip && <venv>/bin/pytest -q`.
- **Swift** (Mac only), if `Sources/`, `Tests/` or `Package.*` changed, or a shared
  resource/schema changed: `swift build && swift test` from the repo root (~30 s).
- **Pre-existing failures:** for every failure, run the same test on `origin/main` (a
  throwaway `git worktree add --detach`). Fails there too → baseline, list it as
  "pre-existing" and leave it. Only on your branch → yours to fix.
- **Real endpoints:** a source change is ideally checked once against the live service.
  If the sandbox blocks it, say so — "mocked only" is a legitimate, stated outcome.

Anything you could not run is **unverified** — the brief must say so.

## Step 5 — PR

- Stage specific paths only (never `git add -A`). Commit messages carry the attribution
  trailer; no personal details.
- Closing keyword: this repo's issue filed by `roznet` → `Closes #N`; outside reporter →
  `Addresses #N` (PR body **and** commit bodies); consumer issue → `For roznet/<repo>#N`,
  no keyword.
- `gh pr create` with a body = short summary + **the full Owner's brief below**, so it
  stands alone there.
- Pushing triggers the review bot. Don't wait on it here — point to `/process-review`.

## Step 6 — The Owner's brief

Print it as your final message **and** put it in the PR body. **≤ ~30 lines**, plain
words, no code unless a name is the clearest handle. Omit a section only when it is
genuinely empty, and then say "none".

**Before writing it, re-read your own diff against this checklist** — the gaps an honest
agent still misses because they're outside what it set out to do:

1. **Departures from the issue.** Every place the implementation differs from what the
   issue or its thread asked, including reversals. Each is a decision for the owner.
2. **Same behaviour, other side.** If you changed how something is parsed or computed,
   does the Python/Swift counterpart now disagree? Do any consumers compute or display
   the same value themselves?
3. **Inherited numbers.** Any figure, interval or premise copied from an old comment,
   docstring or the issue — re-derive it from the code before repeating it.
4. **Growth and cost.** Caches, downloaded files, DB tables or per-call requests that grow
   with input or time: state the bound or "none".
5. **Verified vs claimed.** Only count what's reproducible: tests in the diff and suites
   you ran (with counts). A live check in the session is "checked once, not in the repo".

```
## Owner's brief — <#n | roznet/<repo>#n> <title>

**Kind:** ~70% parser behaviour · 30% public API (additive)   (rough split)
**In one line:** <what this PR does, in plain terms>

**What changes for consumers**
- flyfun-weather: <effect, or "nothing until it calls X">
- flyfun-apps: <effect on the AIRAC build / DB / its app, or "none">
- <other consumer, only if affected>

**Decisions I made for you**   (the ones you might have made differently)
- <choice> — over <alternative>, because <reason>. <"Easy to flip" / "Hard to undo">

**How it could go wrong**
- <concrete failure> → you'd notice it as <symptom / log line / consumer behaviour>

**How we know it works**
- Verified: <e.g. "pytest: 1052 passed, 1 pre-existing failure (test_x)"; "swift test: 110 passed">
- Not verified: <what didn't run, and why>

**Worth making sure you understand**   (2–4 questions specific to this diff)
- <e.g. "Why does an unparseable group now return None instead of raising?">

**Parity:** <Swift counterpart updated / not needed / left — issue #N>
**Design docs:** <docs updated + what was recorded, or "none needed — why">
**Release:** <suggested bump: patch|minor (0.x.y), pip and/or SPM tag, DB rebuild needed?>
**Consumer follow-up:** <e.g. "flyfun-weather: bump pin to >=0.20.0 and pass lookahead=" or "none">

**Pick up on a Mac**   (only what wasn't run here)
- [ ] <exact command, e.g. `swift build && swift test`>

**Follow-ups noticed (not done):** <or "none">
```

Rules for the brief:
- **Lead with what matters to the owner**, not the order you worked in.
- **Questions must be specific to this diff** — where your judgement replaced theirs, a
  number you picked, a behaviour that changed silently. Never generic.
- **Depth follows the classification:** internal can be a few lines; breaking API, parser
  behaviour or schema changes get the full treatment.
- Be honest: an uncompiled Swift change is "written, not compiled", not "done".
