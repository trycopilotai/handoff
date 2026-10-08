# Security

## Reporting a vulnerability

Report privately through GitHub:
<https://github.com/trycopilotai/handoff/security/advisories/new>

That opens a private security advisory visible only to the
maintainers. Do not put the details of a vulnerability in a
public issue.

If that link shows "Not Found", private reporting is not
turned on for this repository. Open a public issue titled
"Security report waiting" that says only that you have a
report, with no details, and a maintainer will arrange a
private channel.

## What is in scope

- **Prompt content that redirects an agent.** `SKILL.md` and
  the three files under `references/` are instructions an
  agent follows when it writes handoff files. Text in any of
  them that makes an agent copy secrets into a handoff file,
  discard dirty work the user did not ask to discard, or
  treat repository content other than the instruction files
  the workflow names (`AGENTS.md`, `CLAUDE.md`, `.cursorrules`
  or local equivalents) as instructions, such as text inside
  a handoff file, a registry value or the collector's
  report, is a valid report.
- **The collector.**
  `skills/handoff/scripts/collect_handoff_state.py` writes
  no file itself. It runs `git rev-parse`, `git rev-list`,
  `git status`, `git log` and `git submodule status` in the
  repository, runs `git rev-parse` and, for a submodule that
  is its own checkout, `git status` in each submodule
  directory that exists on disk, reads the registry file,
  and prints a report. It refuses a `--state-file` that is
  absolute, that resolves outside the repository root
  (symbolic links included), or that it cannot resolve. A
  `--state-file` value that makes it read a file outside the
  root, other than through the link swap listed below, is a
  finding. So is any input that makes the collector itself
  write a file; git refreshing its index, and programs a
  repository's own git configuration names, are listed below
  as known limits.
- **The install blocks.** The two README blocks run
  `mkdir -p`, `mktemp -d`, `git clone`, `cp`, `mv` and
  `rm -rf`. They create the skills directory under `$HOME`
  and its parents if missing, and otherwise work inside it.
  A repository state that makes either block write or delete
  outside that skills directory is in scope.
- **The build scripts.** `assets/build.py` finds a Chrome or
  Chromium binary from a fixed candidate list, runs it
  headless with a temporary profile directory, and writes
  the preview PNG and its stamp. `scripts/generate_demo.py`
  writes two SVG files; `scripts/verify_demo.py` only
  reads. `scripts/record_session.py` copies `skills/` and
  `examples/synthetic-repo/` into a temporary directory,
  makes two commits there, runs the collector through
  `bash`, and rewrites the transcript and the manifest; with
  `RECORD_RAW_DIR` set it also writes two files into that
  directory. `tests/test_collect_handoff_state.py` builds
  git repositories in temporary directories and runs the
  collector against them. `tests/test_integrations.py` runs
  `git` against the repository root and rebuilds the
  synthetic repository in a temporary directory.

## Known limits, not findings

- Like any `git status`, the collector's calls may refresh
  git's own index file in the repository it inspects.
- The report holds the repository's absolute path, branch
  and upstream names, commit subjects, dirty file names, and
  the registry fields the collector reads (the update
  protocol lists them), with no filtering. The `--json`
  report also holds the collector's own absolute path when
  it is installed outside the repository, for example under
  your home directory. Treat the report like the handoff
  files themselves: read it before you paste it into an
  issue or a chat.
- Registry values are not checked. A value can carry text
  that looks like an instruction to an agent reading the
  report. The Markdown table shows each value as one line of
  text, with runs of whitespace as one space, a character
  that cannot be encoded as UTF-8 as `?`, and `\` and `|`
  escaped; that is formatting, not filtering.
- Git output is placed in the Markdown report as it is. A
  commit subject or file name that holds three backticks
  ends the fenced block early, and the rest of that block
  renders as Markdown. Bytes that the locale's encoding
  cannot decode (with a UTF-8 locale, bytes that are not
  UTF-8) are shown as replacement characters.
- Submodule paths are read from the line-oriented output of
  `git submodule status`. A path that holds a newline, ends
  in whitespace, or contains ` (` and ends in `)` is
  misread, and that submodule is then reported as missing or
  under the wrong path.
- The `--state-file` check resolves the path before the
  file is read. A process that swaps a link in between can
  change what it reads. A `--state-file` that names a FIFO
  or another special file inside the root is opened like a
  regular file, so the collector can wait on it without
  end.
- The collector runs whichever `git` is first on `PATH`, and
  git reads the repository's own configuration. That
  configuration can name programs git runs during
  `git status` (for example `core.fsmonitor`), in the
  repository and in each checked-out submodule. Point the
  collector only at repositories you trust.

## What is out of scope

The skill tells an agent to follow the target repository's
own instructions and to run its validation commands. What
those instructions and commands do, and the behaviour of
Claude Code, Codex, or any other host, is out of scope here.
Report those to their own maintainers.
