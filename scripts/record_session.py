#!/usr/bin/env python3
"""Record the collector session again and refresh the evidence manifest.

    python3 scripts/record_session.py

The commands are the ones listed in ``evidence/demo-manifest.json``.
They run in a throwaway directory that holds a copy of ``skills/``, a
git repository named ``demo-repo`` built from
``examples/synthetic-repo/``, and an empty directory named
``not-a-repo``. ``demo-repo`` gets two commits with a fixed author and
date: ``README.md`` and ``greeter.py`` without its ``--version`` flag,
then the handoff files. ``greeter.py`` is then put back as the example
has it, which leaves the flag as the one uncommitted change.

The transcript is laid out as a shell session: each command line, the
command's stdout and stderr together, and an ``echo "exit status: $?"``
line with the exit status; the script writes the command, echo and
status lines itself. One edit is made before it is written: the
throwaway directory's absolute path is replaced with ``/work``.

The commands run with ``GIT_CEILING_DIRECTORIES`` set to the throwaway
directory's parent, so that git cannot find a repository that happens
to contain it, with no global or system git configuration, and with a
directory holding ``python3`` put first on ``PATH``.

The manifest's hashes of ``SKILL.md``, the program, the example and the
transcript are then rewritten, with the UTC date and the interpreter. Run
``make demo`` afterwards to rebuild the images.

Set ``RECORD_RAW_DIR`` to an existing directory to also keep the
unedited capture and the replaced path there. Choose one outside the
repository; the script does not check.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evidence" / "demo-manifest.json"
EXAMPLE = ROOT / "examples" / "synthetic-repo"
PLACEHOLDER = "/work"
IDENTITY = {
    "GIT_AUTHOR_NAME": "Example",
    "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "Example",
    "GIT_COMMITTER_EMAIL": "test@example.com",
}
# The two commits, oldest first: a message, a fixed date, and the
# example files each one adds.
COMMITS = (
    ("Add the greeter", "2026-01-15T09:00:00Z", ["README.md", "greeter.py"]),
    (
        "Record a handoff checkpoint",
        "2026-01-15T10:30:00Z",
        ["HANDOFF.md", "HANDOFF.log.md", "handoff"],
    ),
)
# The uncommitted edit the example's snapshot describes: the first
# commit has greeter.py without these lines.
UNCOMMITTED = (
    '    if argv[:1] == ["--version"]:\n'
    '        print("greeter 0.1.0")\n'
    "        return 0\n"
)
# Files a local tool may leave in the example; the tree hash skips them.
IGNORED = (".DS_Store", "__pycache__")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_sha256(root: Path) -> str:
    """One hash over each file's relative path and SHA-256, in path order.

    Files under a name in IGNORED are skipped.
    """
    digest = hashlib.sha256()
    files = [
        p
        for p in root.rglob("*")
        if p.is_file() and not set(p.relative_to(root).parts) & set(IGNORED)
    ]
    for path in sorted(files):
        digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
        digest.update(sha256(path).encode("ascii") + b"\n")
    return digest.hexdigest()


def git_environment(base: Path) -> dict:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "GIT_CEILING_DIRECTORIES": str(base),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "LC_ALL": "C",
    }


def build_repository(repository: Path, base: Path) -> None:
    shutil.copytree(EXAMPLE, repository, ignore=shutil.ignore_patterns(*IGNORED))
    environment = git_environment(base)
    greeter = repository / "greeter.py"
    final = greeter.read_text(encoding="utf-8")
    if final.count(UNCOMMITTED) != 1:
        raise SystemExit("examples/synthetic-repo/greeter.py changed; update UNCOMMITTED")
    greeter.write_text(final.replace(UNCOMMITTED, ""), encoding="utf-8")

    def git(*arguments: str, extra: dict | None = None) -> None:
        subprocess.run(
            ["git", "-C", str(repository), *arguments],
            env={**environment, **(extra or {})},
            check=True,
            stdout=subprocess.DEVNULL,
        )

    git("init", "--quiet", "-b", "main")
    for message, date, paths in COMMITS:
        git("add", "--", *paths)
        dated = {**IDENTITY, "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date}
        git("commit", "--quiet", "--no-gpg-sign", "-m", message, extra=dated)
    greeter.write_text(final, encoding="utf-8")


def record(commands: list[str], workdir: Path, bindir: Path, base: Path) -> str:
    define, steps = commands[0], commands[1:]
    environment = git_environment(base)
    environment["PATH"] = "%s:%s" % (bindir, environment["PATH"])
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    lines = ["$ " + define]
    for step in steps:
        result = subprocess.run(
            ["bash", "-c", define + "\n" + step],
            cwd=workdir,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        lines.append("$ " + step)
        lines.extend(result.stdout.splitlines())
        lines.append('$ echo "exit status: $?"')
        lines.append("exit status: %d" % result.returncode)
    return "\n".join(lines) + "\n"


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    commands = manifest["invocation"]["commands"]
    with tempfile.TemporaryDirectory() as scratch:
        base = Path(scratch).resolve()
        workdir = base / "capture"
        bindir = base / "bin"
        bindir.mkdir()
        (bindir / "python3").symlink_to(sys.executable)
        shutil.copytree(
            ROOT / "skills",
            workdir / "skills",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        build_repository(workdir / "demo-repo", base)
        (workdir / "not-a-repo").mkdir()
        raw = record(commands, workdir, bindir, base)
        capture_root = str(workdir)

    raw_dir = os.environ.get("RECORD_RAW_DIR")
    if raw_dir:
        Path(raw_dir, "collector-session.source.txt").write_text(raw, encoding="utf-8")
        Path(raw_dir, "collector-session.capture-root.txt").write_text(
            capture_root + "\n", encoding="utf-8"
        )

    transcript = ROOT / manifest["output"]["path"]
    transcript.write_text(raw.replace(capture_root, PLACEHOLDER), encoding="utf-8")

    manifest["date"] = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    manifest["invocation"]["interpreter"] = "Python " + platform.python_version()
    manifest["skill"]["sha256"] = sha256(ROOT / manifest["skill"]["path"])
    for program in manifest["programs"]:
        program["sha256"] = sha256(ROOT / program["path"])
    manifest["example"]["tree_sha256"] = tree_sha256(ROOT / manifest["example"]["path"])
    manifest["output"]["sha256"] = sha256(transcript)
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("wrote %s" % transcript.relative_to(ROOT))
    print("wrote %s" % MANIFEST.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
