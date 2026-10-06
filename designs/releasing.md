# Releasing & Versioning

> Two packages released independently from this mono-repo with separate tag conventions

## Intent

This repo produces two distributable packages — a Python pip package and a Swift SPM package. They version and release independently because they evolve at different paces. The tag format distinguishes them so SPM and pip don't interfere with each other.

## Tag Conventions

| Package | Tag format | Example | Install |
|---------|-----------|---------|---------|
| Python pip (`euro_aip`) | `v0.x.y` (v prefix) | `v0.3.0` | `pip install euro-aip` |
| Swift SPM (`RZFlight`) | `1.x.y` (no prefix) | `1.3.0` | `.package(url: "...", from: "1.3.0")` |

SPM resolves versions from tags without `v` prefix. The `v`-prefixed pip tags are ignored by SPM resolution.

The `/release` skill (`.claude/skills/release/SKILL.md`) runs this procedure end to end:
it works out the bump, runs both suites, and waits for confirmation before uploading and
tagging. PRs don't bump the version (concurrent PRs would claim the same number); the
bump happens at release time, unless a PR already carries one.

## Releasing Python (euro_aip)

1. Bump version in **both** files (must match):
   - `euro_aip/pyproject.toml` → `version = "0.3.0"`
   - `euro_aip/euro_aip/__init__.py` → `__version__ = '0.3.0'`
2. Commit the version bump
3. Build: `cd euro_aip && make build`
4. Publish: `twine upload dist/*`
5. Tag: `git tag v0.3.0 && git push origin v0.3.0`

## Releasing Swift (RZFlight)

1. No version file to update — version comes from the git tag
2. Tag at the commit to release: `git tag 1.3.0 && git push origin 1.3.0`
3. In practice every Swift consumer tracks `branch = main`, not a tag (see
   `consumers.md`), so merging to `main` already ships Swift changes; the tag is a marker

## Gotchas

- **Two version files for Python**: `pyproject.toml` is the build system source of truth, `__init__.py` is what `import euro_aip; euro_aip.__version__` returns. Keep them in sync.
- **Don't use bare semver for pip**: Tags like `0.3.0` (no prefix) would be picked up by SPM as a Swift package version. Always use `v` prefix for pip releases.
- **Swift has no version gate**: because consumers track `main`, a breaking Swift change reaches the apps on their next package update — flag it in the PR, there is no version bump to signal it.
- **Independent cadence**: A Swift-only change doesn't need a pip release, and vice versa. Tag whichever package changed.
