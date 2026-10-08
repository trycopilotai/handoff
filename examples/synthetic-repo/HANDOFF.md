---
name: Repository Handoff
last_updated: 2026-01-15T10:30:00Z
status: active
active_objective: Add a --version flag to greeter.py
resume_here: Add a test for --version, then commit greeter.py with it
handoff_log: HANDOFF.log.md
---

# Repository Handoff

## Purpose And Rules

- This file is the current implementation snapshot for an
  explicit handoff/checkpoint/resume invocation.
- Do not update it as automatic end-of-turn bookkeeping for
  ordinary implementation work.
- Keep history in `HANDOFF.log.md`.
- Do not include secrets.

## Resume Here

Add a test that runs `python3 greeter.py --version` and
expects `greeter 0.1.0` with exit status 0. Run it. Then
commit `greeter.py` together with the test.

## Current Repo Graph

One repository on `main`, no upstream, no submodules. HEAD
is the commit that added this snapshot.

## Current Working State

- `greeter.py` is modified: the `--version` flag, owned by
  the cli lane. Keep it.
- Nothing else is dirty.

## Agent Ownership Index

| Scope | Owner   | Model / Surface       | Session   | Status  | Detail                | Updated    |
| ----- | ------- | --------------------- | --------- | ------- | --------------------- | ---------- |
| cli   | agent-a | model-a / Claude Code | session-a | active  | handoff/agents/cli.md | 2026-01-15 |
| docs  | agent-b | model-b / Codex       | session-b | waiting | none                  | 2026-01-15 |

Agents should read per-agent detail files only when assigned,
linked from a relevant row, or needed for conflict resolution.

## Active Objective

Add a `--version` flag to `greeter.py` that prints
`greeter 0.1.0` and exits 0, with a test, and document it in
`README.md`.

## Recent Completed Work

- The greeter and its README, in the first commit.

## Next Work Queue

1. cli lane: add the `--version` test and commit it with
   `greeter.py`.
2. docs lane: add the `--version` line to `README.md`.

## Known Dirty State

- `greeter.py`: the uncommitted `--version` flag. Expected.

## Validation State

- Not run. No test covers the flag yet, and the flag has
  not been run.

## Command Surface

- `python3 greeter.py Ada`
- `python3 greeter.py --version`

## Protocols

None beyond this file and `HANDOFF.log.md`.

## Private / Shareable Boundary

Nothing in this example is private.

## Do-Not-Do List

- Do not revert or stash `greeter.py`.
- Do not edit `README.md` from the cli lane.

## Last Update Checklist

- [x] Snapshot reflects current dirty state.
- [x] Log has a state-transition entry if needed.
- [x] Validation state is current.
- [x] Provenance / memory systems handled if local rules
      require them. This repository has none.
