# Contributing

## Checks

Before each commit, run Vale, Ruff and the tests:

```bash
vale sync
vale .
uvx ruff@0.17.4 format --check .
uvx ruff@0.17.4 check .
python3 -m unittest
```

The Ruff commands require [uv](https://docs.astral.sh/uv/). The tests require
Python 3.11 or later and no other packages.

## Release

The public surface consists of the manifest format, the arguments of the skill
and the output of `plan.py`. A change to the public surface must have an entry
in `CHANGELOG.md`. Before 1.0, a breaking change must increment the minor
version.

To release a version:

1. In a release commit, rename the section `[Unreleased]` of `CHANGELOG.md` to
   the version and its date, such as `[0.1.0] - 2026-11-14`, and add an empty
   section `[Unreleased]` above it.
2. Push the tag `v<version>` on that commit.

The tag triggers the release workflow, which runs the checks and creates a
GitHub release with the version's CHANGELOG section as its notes. The workflow
fails when that section is missing from `CHANGELOG.md`.
