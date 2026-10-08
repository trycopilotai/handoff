#!/usr/bin/env python3
"""Tests for skills/handoff/scripts/collect_handoff_state.py.

Each test builds a throwaway git repository and runs the
collector as a subprocess, the way the skill tells an agent
to run it. Standard library and `git` only:

    python3 tests/test_collect_handoff_state.py
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLLECTOR = ROOT / "skills" / "handoff" / "scripts" / "collect_handoff_state.py"
AGENTS = {
    "schema_version": 1,
    "updated_at": "2026-01-15T10:30:00Z",
    "agents": [
        {
            "agent_id": "cli",
            "owner": "agent-a",
            "model": "model-a",
            "surface": "Claude Code",
            "chat_uuid": "session-a",
            "status": "active",
            "detail_path": "handoff/agents/cli.md",
            "owned_scopes": [{"name": "cli", "paths": ["greeter.py"]}],
            "updated_at": "2026-01-15T10:30:00Z",
        },
        {"agent_id": "docs", "owned_scopes": [{"name": "docs"}, "not-a-scope"]},
    ],
}


class Repository:
    """A throwaway repository with one commit, isolated from any parent."""

    def __init__(self) -> None:
        self._directory = tempfile.TemporaryDirectory()
        self.base = Path(self._directory.name).resolve()
        self.path = self.base / "repo"
        self.path.mkdir()
        self.environment = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "GIT_CEILING_DIRECTORIES": str(self.base),
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "Example",
            "GIT_AUTHOR_EMAIL": "test@example.com",
            "GIT_COMMITTER_NAME": "Example",
            "GIT_COMMITTER_EMAIL": "test@example.com",
            "LC_ALL": "C",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        self.git("init", "--quiet", "-b", "main")
        self.write("README.md", "example\n")
        self.git("add", "README.md")
        self.git("commit", "--quiet", "--no-gpg-sign", "-m", "First")

    def close(self) -> None:
        self._directory.cleanup()

    def git(self, *arguments: str, cwd: Path | None = None) -> str:
        if cwd is None:
            cwd = self.path
        return subprocess.run(
            ["git", "-C", str(cwd), *arguments],
            env=self.environment,
            check=True,
            capture_output=True,
            text=True,
        ).stdout

    def write(self, relative: str, text: str) -> Path:
        path = self.path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def collect(self, *arguments: str, repo: str | None = None):
        if repo is None:
            repo = str(self.path)
        return subprocess.run(
            [sys.executable, str(COLLECTOR), "--repo", repo, *arguments],
            env=self.environment,
            capture_output=True,
            text=True,
        )

    def report(self, *arguments: str) -> dict:
        result = self.collect("--json", *arguments)
        if result.returncode != 0:
            raise AssertionError(result.stderr)
        return json.loads(result.stdout)


class CollectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Repository()
        self.addCleanup(self.repo.close)

    def table_rows(self, markdown: str) -> list:
        section = markdown.split("## Agent Ownership Summary", 1)[1]
        return [line for line in section.splitlines() if line.startswith("| ")][1:]

    def test_markdown_report_prints_one_row_per_agent(self) -> None:
        self.repo.write("handoff/state.json", json.dumps(AGENTS))
        result = self.repo.collect()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("# Handoff State Collection\n"))
        rows = self.table_rows(result.stdout)
        self.assertEqual(rows[0], "| --- | --- | --- | --- | --- | --- | --- |")
        self.assertEqual(
            rows[1:],
            [
                "| agent-a | model-a / Claude Code | session-a | active "
                "| handoff/agents/cli.md | cli | 2026-01-15T10:30:00Z |",
                "| docs | / |  |  |  | docs |  |",
            ],
        )

    def test_json_report_keeps_the_first_dirty_line_intact(self) -> None:
        self.repo.write("README.md", "changed\n")
        self.repo.write("new.txt", "x\n")
        data = self.repo.report()
        self.assertEqual(data["dirty_files"], [" M README.md", "?? new.txt"])
        self.assertEqual(data["branch"], "main")
        self.assertEqual(data["repo"], str(self.repo.path))
        self.assertEqual(data["full_head"], self.repo.git("rev-parse", "HEAD").strip())
        self.assertEqual(data["upstream"], "")
        self.assertIsNone(data["ahead"])

    def test_registry_fields_are_reported_and_bad_scopes_skipped(self) -> None:
        self.repo.write("handoff/state.json", json.dumps(AGENTS))
        state = self.repo.report()["handoff_state"]
        self.assertTrue(state["present"])
        self.assertEqual(state["path"], "handoff/state.json")
        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(state["agents"][0]["owned_scopes"], [{"name": "cli", "paths": ["greeter.py"]}])
        self.assertEqual(state["agents"][1]["owned_scopes"], [{"name": "docs", "paths": []}])
        self.assertEqual(state["agents"][1]["owner"], "")

    def test_missing_registry_is_reported_not_an_error(self) -> None:
        result = self.repo.collect()
        self.assertEqual(result.returncode, 0)
        self.assertIn("_No handoff/state.json present._", result.stdout)
        self.assertFalse(self.repo.report()["handoff_state"]["present"])

    def test_state_file_option_reads_another_relative_path(self) -> None:
        self.repo.write("ops/lanes.json", json.dumps(AGENTS))
        state = self.repo.report("--state-file", "ops/lanes.json")["handoff_state"]
        self.assertEqual(state["path"], "ops/lanes.json")
        self.assertEqual(len(state["agents"]), 2)
        result = self.repo.collect("--state-file", "ops/missing.json")
        self.assertIn("_No ops/missing.json present._", result.stdout)

    def test_state_file_outside_the_root_is_refused_with_status_two(self) -> None:
        outside = self.repo.base / "outside.json"
        outside.write_text(json.dumps(AGENTS), encoding="utf-8")
        (self.repo.path / "link.json").symlink_to(outside)
        (self.repo.path / "loop.json").symlink_to(self.repo.path / "loop.json")
        values = (str(outside), "../outside.json", "handoff/../../outside.json", "link.json", "loop.json")
        for value in values:
            result = self.repo.collect("--state-file", value)
            self.assertEqual(result.returncode, 2, value)
            self.assertEqual(result.stdout, "", value)
            self.assertIn("--state-file must be a relative path that resolves inside", result.stderr)
            self.assertNotIn("Traceback", result.stderr, value)

    def test_repo_is_checked_before_the_state_file(self) -> None:
        plain = self.repo.base / "plain"
        plain.mkdir()
        result = self.repo.collect("--state-file", "../x.json", repo=str(plain))
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a git repository: ", result.stderr)

    def test_a_directory_that_is_not_a_repository_exits_one(self) -> None:
        plain = self.repo.base / "plain"
        plain.mkdir()
        for repo in (str(plain), str(self.repo.base / "absent")):
            result = self.repo.collect(repo=repo)
            self.assertEqual(result.returncode, 1, repo)
            self.assertEqual(result.stdout, "")
            self.assertIn("not a git repository: ", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_a_subdirectory_reports_the_top_level(self) -> None:
        self.repo.write("deep/er/file.txt", "x\n")
        result = self.repo.collect("--json", repo=str(self.repo.path / "deep" / "er"))
        self.assertEqual(json.loads(result.stdout)["repo"], str(self.repo.path))

    def test_unparsable_or_misshapen_registries_are_reported_in_the_output(self) -> None:
        cases = {
            "{not json": None,
            "[]": "the top level is not a JSON object",
            '{"agents": {}}': "agents is not a list",
            '{"agents": [1]}': "agents[0] is not an object",
            '{"agents": [{"owned_scopes": "x"}]}': "agents[0].owned_scopes is not a list",
        }
        for text, message in cases.items():
            self.repo.write("handoff/state.json", text)
            result = self.repo.collect()
            self.assertEqual(result.returncode, 0, text)
            self.assertNotIn("Traceback", result.stderr, text)
            self.assertIn("`handoff/state.json` could not be parsed: ", result.stdout, text)
            state = self.repo.report()["handoff_state"]
            self.assertEqual(state["agents"], [], text)
            if message is not None:
                self.assertEqual(state["error"], message, text)

    def test_output_that_is_not_utf8_does_not_stop_the_report(self) -> None:
        # `git commit` would re-encode the message, so write the
        # commit object directly.
        tree = self.repo.git("rev-parse", "HEAD^{tree}").strip()
        parent = self.repo.git("rev-parse", "HEAD").strip()
        person = b"Example <test@example.com> 1700000000 +0000"
        body = b"tree %s\nparent %s\nauthor %s\ncommitter %s\n\nSubject \xff\xfe\n" % (
            tree.encode(), parent.encode(), person, person)
        commit = subprocess.run(
            ["git", "-C", str(self.repo.path), "hash-object", "-t", "commit", "-w", "--stdin"],
            input=body, env=self.repo.environment, capture_output=True, check=True,
        ).stdout.decode().strip()
        self.repo.git("update-ref", "HEAD", commit)
        result = self.repo.collect()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Subject \ufffd\ufffd", result.stdout)

    def test_submodules_with_spaces_and_without_a_checkout(self) -> None:
        library = self.repo.base / "library"
        library.mkdir()
        self.repo.git("init", "--quiet", "-b", "main", cwd=library)
        self.repo.git("commit", "--quiet", "--no-gpg-sign", "--allow-empty", "-m", "L", cwd=library)
        self.repo.git("-c", "protocol.file.allow=always", "submodule", "add", "--quiet",
                      str(library), "lib dir")
        self.repo.git("commit", "--quiet", "--no-gpg-sign", "-m", "Add lib dir")
        (self.repo.path / "lib dir" / "inside.txt").write_text("x\n", encoding="utf-8")
        clone = self.repo.base / "clone"
        self.repo.git("clone", "--quiet", str(self.repo.path), str(clone), cwd=self.repo.base)
        (clone / "parent-only.txt").write_text("x\n", encoding="utf-8")

        checked_out = self.repo.report()["submodule_details"]
        self.assertEqual([d["path"] for d in checked_out], ["lib dir"])
        self.assertIs(checked_out[0]["checked_out"], True)
        self.assertIn("?? inside.txt", checked_out[0]["status"])

        result = self.repo.collect("--json", repo=str(clone))
        details = json.loads(result.stdout)["submodule_details"]
        self.assertEqual(details, [{"path": "lib dir", "exists": True, "checked_out": False, "status": []}])
        markdown = self.repo.collect(repo=str(clone)).stdout
        self.assertIn("### lib dir\nnot checked out\n", markdown)
        self.assertNotIn("parent-only.txt", markdown.split("## Nested Submodule Status", 1)[1])

    def test_null_values_render_empty_in_every_cell(self) -> None:
        state = {"agents": [{"agent_id": "x", "owner": None, "model": None, "surface": None,
                             "chat_uuid": None, "status": None, "detail_path": None,
                             "updated_at": None, "owned_scopes": [{"name": None}, {"name": "b"}]}]}
        self.repo.write("handoff/state.json", json.dumps(state))
        result = self.repo.collect()
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.table_rows(result.stdout)
        self.assertEqual(rows[1:], ["| x | / |  |  |  | , b |  |"])
        self.assertNotIn("None", result.stdout.split("## Agent Ownership Summary", 1)[1])

    def test_agent_id_replaces_only_a_missing_null_or_empty_owner(self) -> None:
        agents = [
            {"agent_id": "missing"},
            {"agent_id": "null", "owner": None},
            {"agent_id": "empty", "owner": ""},
            {"agent_id": "zero", "owner": 0},
            {"agent_id": "false", "owner": False},
        ]
        self.repo.write("handoff/state.json", json.dumps({"agents": agents}))
        rows = self.table_rows(self.repo.collect().stdout)[1:]
        self.assertEqual([row.split(" | ")[0] for row in rows],
                         ["| missing", "| null", "| empty", "| 0", "| false"])

    def test_backslashes_are_escaped_before_pipes(self) -> None:
        state = {"agents": [{"owner": "a\\|b", "status": "c\\d"}]}
        self.repo.write("handoff/state.json", json.dumps(state))
        rows = self.table_rows(self.repo.collect().stdout)
        self.assertEqual(rows[1:], ["| a\\\\\\|b | / |  | c\\\\d |  |  |  |"])

    def test_a_lone_surrogate_does_not_stop_the_markdown_report(self) -> None:
        self.repo.write("handoff/state.json", '{"agents": [{"owner": "a\\ud800b"}]}')
        result = self.repo.collect()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.table_rows(result.stdout)[1:], ["| a?b | / |  |  |  |  |  |"])

    def test_a_parent_that_is_a_file_reports_the_registry_missing(self) -> None:
        self.repo.write("handoff", "a script, not a directory\n")
        result = self.repo.collect()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("_No handoff/state.json present._", result.stdout)
        self.assertFalse(self.repo.report()["handoff_state"]["present"])

    def test_table_cells_stay_on_one_line_with_pipes_escaped(self) -> None:
        state = {
            "agents": [
                {"owner": "a|b", "status": 3, "chat_uuid": "two\nlines", "detail_path": None,
                 "owned_scopes": [{"name": 7}, {"name": "x|y"}]}
            ]
        }
        self.repo.write("handoff/state.json", json.dumps(state))
        result = self.repo.collect()
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = self.table_rows(result.stdout)
        self.assertEqual(rows[1:], ["| a\\|b | / | two lines | 3 |  | 7, x\\|y |  |"])

    def test_the_collector_changes_no_file_outside_git_metadata(self) -> None:
        self.repo.write("handoff/state.json", json.dumps(AGENTS))
        self.repo.write("README.md", "dirty\n")

        def snapshot() -> dict:
            files = {}
            for path in sorted(self.repo.base.rglob("*")):
                if ".git" in path.relative_to(self.repo.base).parts:
                    continue
                if path.is_file():
                    files[str(path)] = path.read_bytes()
            return files

        before = snapshot()
        status = self.repo.git("status", "--porcelain=v1")
        self.assertEqual(self.repo.collect().returncode, 0)
        self.assertEqual(self.repo.collect("--json").returncode, 0)
        self.assertEqual(snapshot(), before)
        self.assertEqual(self.repo.git("status", "--porcelain=v1"), status)


if __name__ == "__main__":
    unittest.main()
