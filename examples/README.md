# Worked example

This is synthetic example material. The project, the agents,
the sessions and the dates in `synthetic-repo/` are made up
for this example, and the handoff files were written by hand
for this release; no agent produced them by running the
skill, and none of it was copied from a real handoff.

`synthetic-repo/` is a small repository at an explicit
handoff checkpoint of two agent lanes, laid out with the
skill's default paths:

- `HANDOFF.md`, the snapshot, filled in from
  `skills/handoff/references/snapshot-template.md`;
- `HANDOFF.log.md`, the log, with two entries in the shape
  of `skills/handoff/references/log-entry-template.md`;
- `handoff/state.json`, the registry, with two agent lanes;
- `handoff/agents/cli.md`, the one per-agent detail file a
  registry row links to;
- `greeter.py` and `README.md`, the project itself.

`greeter.py` here is the working-tree version, with the
uncommitted `--version` flag the snapshot describes.
`scripts/record_session.py` copies `synthetic-repo/` into a
throwaway directory and makes two commits with a fixed
author and date: first `README.md` and `greeter.py` without
the flag, then the handoff files. It then puts `greeter.py`
back as it is here, so the repository has the one
uncommitted change the snapshot describes, and runs the
collector against it. The result is
`evidence/transcripts/collector-session.txt`.
