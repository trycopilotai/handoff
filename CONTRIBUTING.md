# Contributing

This repository is one skill, one small program with its
tests, a worked example, and the scripts that build and
check the demo images.

## Run the checks first

```sh
make check
```

That runs `tests/test_collect_handoff_state.py` and
`tests/test_integrations.py`. Both need Python 3.9 or later
and `git` 2.32 or later, and nothing else: every git command
the tests run is isolated from your global and system git
configuration with `GIT_CONFIG_GLOBAL` and
`GIT_CONFIG_NOSYSTEM`. The second needs a git checkout with
its full history and tags: it reads `git log` for every
commit, and when `HEAD` carries a release tag it checks that
tag against the manifests.

**The packaging contract asserts on the README.** These will
fail on an innocent-looking prose edit:

- the claim line at the top of the README must appear
  verbatim, and the recorded transcript must show one table
  row for each agent in the example's registry;
- each install block must carry its own `release=` pin at
  the version both plugin manifests ship;
- `SKILL.md` must stay under 500 lines;
- `evidence/demo-manifest.json` records the SHA-256 of
  `SKILL.md`, of the collector, of the files under
  `examples/synthetic-repo/` (except `.DS_Store` and
  `__pycache__` files) and of the transcript, so any edit to
  one of those, prose included, fails until the manifest is
  refreshed as
  described next.

If you change one of those, change the thing it describes
too.

## Changing the program, the skill or the example

After any edit to `SKILL.md`, to the collector, or to a file
under `examples/synthetic-repo/`, run:

```sh
make record
make demo
```

`make record` runs `scripts/record_session.py`. It rebuilds
the synthetic repository in a throwaway directory, replays
the commands listed in the manifest there, writes the
transcript with that directory's path replaced by `/work`,
and rewrites the manifest's hashes, date and interpreter. It
needs `bash`, `git` and `python3`. The transcript carries
the time of the run, so it usually changes even when the
program did not.

`make demo` rebuilds the two images from the transcript.
`make assets` rebuilds the social preview and needs Chrome
or Chromium; `make asset-check` does not.

To check the recorded session, run `make record` in a fresh
clone and `git diff`. With the program and the example
unchanged, and git 2.50.1 as when it was recorded, the
transcript differs only in its `Generated UTC` line; another
git version may word git's own lines differently. In the manifest the transcript's
SHA-256 differs, `date` differs on a different UTC day, and
`interpreter` differs under a different Python version. The
commit ids are fixed by the recorder's author and dates.

## What is most useful

Open an issue for any of these. The labels
`good first issue` and `help wanted` mark the ones that are
ready to pick up.

- **A handoff another agent could not resume from.** Say
  what the snapshot left out and what the next agent did
  instead. Remove anything private first.
- **A repository state the collector reports wrongly.** Say
  which git command shows the state, and what the report
  says instead.
- **A registry field the collector should read.** Say which
  host or workflow writes it.

## Pull requests

Prose changes to `SKILL.md` and the files under
`references/` are welcome. Say what an agent wrote before
the change and what it writes after, on the same
repository.

Keep `SKILL.md` under 500 lines; the suite enforces it.
Frontmatter carries `name` and `description` and nothing
else.

The top-level `skill` is a symlink to `skills/handoff/`. Do
not reverse that orientation.

Commit with your own identity and no `Co-authored-by`
trailer of any kind. The suite fails on one anywhere in
history, so do not apply review suggestions through the
GitHub UI.
