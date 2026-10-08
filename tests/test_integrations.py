#!/usr/bin/env python3
"""The packaging contract.

Facts this repository states in more than one place are
pinned here where a script can compare them: the name and
version, the claim and the transcript behind it, the worked
example, the demo images, the install blocks, and the
evidence hashes.

Runs offline with the standard library and `git`:

    python3 tests/test_integrations.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import struct
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "handoff"
PACKAGE = ROOT / "skills" / NAME
COLLECTOR = PACKAGE / "scripts" / "collect_handoff_state.py"
SKILL = PACKAGE / "SKILL.md"
README = ROOT / "README.md"
EXAMPLE = ROOT / "examples" / "synthetic-repo"
TRANSCRIPT = ROOT / "evidence" / "transcripts" / "collector-session.txt"
MANIFEST = ROOT / "evidence" / "demo-manifest.json"
CLAIM = "The collector prints one table row per agent in state.json."
REPOSITORY = "https://github.com/trycopilotai/" + NAME
DEFAULT_PATHS = ("HANDOFF.md", "HANDOFF.log.md", "handoff/state.json", "handoff/agents/")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def flat(path: Path) -> str:
    return " ".join(read(path).split())


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments: str) -> str:
    """Run git at the repository root with no global or system config."""
    environment = dict(os.environ)
    environment["GIT_CONFIG_GLOBAL"] = os.devnull
    environment["GIT_CONFIG_NOSYSTEM"] = "1"
    return subprocess.run(
        ["git", *arguments],
        cwd=str(ROOT),
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest(product: str) -> dict:
    return json.loads(read(ROOT / product / "plugin.json"))


def frontmatter(text: str) -> dict:
    """The `key: value` pairs between the two `---` lines."""
    lines = text.splitlines()
    if lines[0] != "---":
        raise AssertionError("SKILL.md does not open with frontmatter")
    end = lines.index("---", 1)
    fields: dict = {}
    key = None
    for line in lines[1:end]:
        match = re.match(r"^([a-z_-]+):\s*(.*)$", line)
        if match:
            key = match.group(1)
            fields[key] = match.group(2).strip()
            continue
        if key is None or not line.startswith(" "):
            raise AssertionError("unexpected frontmatter line: " + line)
        fields[key] = (fields[key] + " " + line.strip()).strip()
    for name, value in fields.items():
        if value.startswith(">-"):
            fields[name] = value[2:].strip()
    return fields


def interface_yaml(text: str) -> dict:
    """The quoted scalars under `interface:` in agents/openai.yaml."""
    lines = text.splitlines()
    if lines[0] != "interface:":
        raise AssertionError("openai.yaml does not start with interface:")
    fields: dict = {}
    key = None
    for line in lines[1:]:
        match = re.match(r"^  ([a-z_]+):\s*(.*)$", line)
        if match:
            key = match.group(1)
            fields[key] = match.group(2).strip()
            continue
        fields[key] = (fields[key] + " " + line.strip()).strip()
    for name, value in fields.items():
        if not (value.startswith('"') and value.endswith('"')):
            raise AssertionError(name + " is not a double-quoted scalar")
        fields[name] = value[1:-1]
    return fields


def install_blocks() -> list:
    return re.findall(r"```sh\nset -eu\n(.*?)```", read(README), flags=re.S)


def transcript_steps() -> dict:
    """Each command line in the transcript, mapped to its output lines."""
    steps: dict = {}
    current = None
    for line in read(TRANSCRIPT).splitlines():
        if line.startswith("$ echo "):
            current = None
            continue
        if line.startswith("$ "):
            current = line[2:]
            steps[current] = []
            continue
        if current is not None:
            steps[current].append(line)
    return steps


def exit_status_after(command: str) -> int:
    lines = read(TRANSCRIPT).splitlines()
    index = lines.index("$ " + command)
    marker = lines.index('$ echo "exit status: $?"', index)
    return int(lines[marker + 1].split(": ")[1])


class LayoutTest(unittest.TestCase):
    def test_skill_is_a_symlink_into_the_canonical_package(self) -> None:
        link = ROOT / "skill"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(str(link)), "skills/" + NAME)
        self.assertFalse(PACKAGE.is_symlink())

    def test_package_holds_what_the_readme_says_it_installs(self) -> None:
        for relative in (
            "SKILL.md",
            "agents/openai.yaml",
            "references/update-protocol.md",
            "references/snapshot-template.md",
            "references/log-entry-template.md",
            "scripts/collect_handoff_state.py",
        ):
            self.assertTrue((PACKAGE / relative).is_file(), relative)
        self.assertEqual(
            sorted(path.name for path in PACKAGE.iterdir()),
            ["SKILL.md", "agents", "references", "scripts"],
        )

    def test_history_has_no_co_author_trailer(self) -> None:
        messages = git("log", "--all", "--format=%B")
        self.assertNotIn("co-authored-by", messages.lower())


class SkillTest(unittest.TestCase):
    def test_frontmatter_is_name_and_description_only(self) -> None:
        fields = frontmatter(read(SKILL))
        self.assertEqual(sorted(fields), ["description", "name"])
        self.assertEqual(fields["name"], NAME)
        self.assertRegex(NAME, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(NAME), 64)
        self.assertTrue(fields["description"])
        self.assertLessEqual(len(fields["description"]), 1024)

    def test_skill_stays_under_five_hundred_lines(self) -> None:
        self.assertLess(len(read(SKILL).splitlines()), 500)

    def test_files_the_skill_points_at_exist(self) -> None:
        text = read(SKILL)
        for relative in (
            "scripts/collect_handoff_state.py",
            "references/update-protocol.md",
            "references/snapshot-template.md",
            "references/log-entry-template.md",
        ):
            self.assertIn(relative, text)
            self.assertTrue((PACKAGE / relative).is_file(), relative)

    def test_collector_invocations_name_the_skill_directory(self) -> None:
        # The agent runs from the target repository, so a bare
        # `python3 scripts/...` cannot find the collector.
        documents = [SKILL, *sorted((PACKAGE / "references").glob("*.md"))]
        calls = []
        for document in documents:
            for call in re.findall(r"python3 (\S*scripts/collect_handoff_state\.py)", read(document)):
                calls.append(call)
                self.assertEqual(call.split("scripts/")[0], "<skill-dir>/", document.name)
        self.assertGreaterEqual(len(calls), 3)
        self.assertIn("`<skill-dir>`", read(SKILL))

    def test_skill_and_readme_name_the_same_default_paths(self) -> None:
        collector = load(COLLECTOR, "collect_handoff_state")
        self.assertEqual(collector.DEFAULT_STATE_FILE, "handoff/state.json")
        for document in (SKILL, README):
            text = read(document)
            for path in DEFAULT_PATHS:
                self.assertIn("`%s`" % path, text, document.name)
            self.assertIn("--state-file", text, document.name)

    def test_documented_exit_statuses_match_the_collector(self) -> None:
        for document in (SKILL, README):
            text = flat(document)
            self.assertIn("exits 0 after printing the report, 1 when `--repo` is not inside a git working tree, and 2 on a usage error", text)
        self.assertEqual(exit_status_after("collect --repo demo-repo --recent 2"), 0)
        self.assertEqual(exit_status_after("collect --repo demo-repo --state-file ../outside.json"), 2)
        self.assertEqual(exit_status_after("collect --repo not-a-repo"), 1)


class ManifestTest(unittest.TestCase):
    def test_both_manifests_agree(self) -> None:
        claude = manifest(".claude-plugin")
        codex = manifest(".codex-plugin")
        for field in (
            "name",
            "version",
            "description",
            "license",
            "homepage",
            "repository",
            "skills",
        ):
            self.assertEqual(claude[field], codex[field], field)
        self.assertEqual(claude["name"], NAME)
        self.assertEqual(claude["skills"], "./skills/")
        self.assertEqual(claude["repository"], REPOSITORY)
        self.assertEqual(claude["license"], "MIT")
        self.assertRegex(claude["version"], r"^\d+\.\d+\.\d+$")

    def test_a_release_tag_on_head_is_the_manifest_version(self) -> None:
        tags = git("tag", "--points-at", "HEAD").split()
        releases = [tag for tag in tags if tag.startswith("v")]
        if not releases:
            self.skipTest("HEAD carries no release tag")
        self.assertEqual(releases, ["v" + manifest(".claude-plugin")["version"]])

    def test_codex_interface_matches_the_agent_file(self) -> None:
        interface = manifest(".codex-plugin")["interface"]
        for field in (
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
            "websiteURL",
        ):
            self.assertTrue(interface.get(field), field)
        prompts = interface["defaultPrompt"]
        self.assertEqual(len(prompts), 1)
        self.assertIn("$" + NAME, prompts[0])
        agent = interface_yaml(read(PACKAGE / "agents" / "openai.yaml"))
        self.assertEqual(agent["default_prompt"], prompts[0])
        self.assertEqual(agent["display_name"], interface["displayName"])
        self.assertEqual(agent["short_description"], interface["shortDescription"])


class ReadmeTest(unittest.TestCase):
    def test_claim_is_on_its_own_line(self) -> None:
        self.assertIn(CLAIM, read(README).splitlines())
        self.assertLessEqual(len(CLAIM), 60)

    def test_transcript_shows_one_row_per_agent_in_the_example(self) -> None:
        agents = json.loads(read(EXAMPLE / "handoff" / "state.json"))["agents"]
        output = transcript_steps()["collect --repo demo-repo --recent 2"]
        section = output[output.index("## Agent Ownership Summary") :]
        rows = [line for line in section if line.startswith("| ")]
        self.assertEqual(rows[0], "| Agent | Model / Surface | Session | Status | Detail | Scopes | Updated |")
        self.assertEqual(len(rows[2:]), len(agents))
        self.assertGreaterEqual(len(agents), 2)
        for row, agent in zip(rows[2:], agents):
            self.assertTrue(row.startswith("| %s | " % agent["owner"]), row)
            self.assertIn(" | %s | " % agent["chat_uuid"], row)

    def test_each_install_block_pins_the_manifest_version(self) -> None:
        version = manifest(".claude-plugin")["version"]
        blocks = install_blocks()
        self.assertEqual(len(blocks), 2)
        roots = []
        for block in blocks:
            self.assertEqual(
                re.findall(r"^release=(\S+)$", block, flags=re.M),
                ["v" + version],
            )
            self.assertIn(REPOSITORY + " \\\n", block)
            self.assertIn('--branch "$release"', block)
            target = re.findall(r'^install_target="\$HOME/(\S+)"$', block, flags=re.M)
            self.assertEqual(len(target), 1)
            roots.append(target[0])
        self.assertEqual(
            sorted(roots),
            [".agents/skills/" + NAME, ".claude/skills/" + NAME],
        )

    def test_relative_links_resolve(self) -> None:
        targets = re.findall(r"\]\(([^)#]+)\)", read(README))
        self.assertTrue(targets)
        for target in targets:
            if target.startswith("http"):
                continue
            self.assertTrue((ROOT / target).exists(), target)

    def test_readme_says_what_was_not_measured(self) -> None:
        text = flat(README)
        self.assertIn("No agent invoked the skill", text)
        self.assertIn("has not been measured", text)

    def test_demo_is_offered_with_a_reduced_motion_poster(self) -> None:
        text = read(README)
        picture = re.search(r"<picture>(.*?)</picture>", text, flags=re.S)
        self.assertIsNotNone(picture)
        body = picture.group(1)
        self.assertIn('media="(prefers-reduced-motion: reduce)"', body)
        self.assertIn('srcset="assets/poster.svg"', body)
        self.assertIn('src="assets/demo.svg"', body)


class EvidenceTest(unittest.TestCase):
    def test_manifest_hashes_match_the_files(self) -> None:
        record = json.loads(read(MANIFEST))
        recorder = load(ROOT / "scripts" / "record_session.py", "record_session")
        self.assertEqual(record["skill"]["sha256"], sha256(SKILL))
        programs = {item["path"]: item["sha256"] for item in record["programs"]}
        self.assertEqual(programs, {str(COLLECTOR.relative_to(ROOT)): sha256(COLLECTOR)})
        self.assertEqual(record["example"]["path"], str(EXAMPLE.relative_to(ROOT)))
        self.assertEqual(record["example"]["tree_sha256"], recorder.tree_sha256(EXAMPLE))
        self.assertEqual(record["output"]["sha256"], sha256(TRANSCRIPT))
        self.assertIs(record["output"]["edited"], True)
        self.assertIs(record["agent"]["invoked_the_skill"], False)

    def test_manifest_commands_are_the_ones_in_the_transcript(self) -> None:
        record = json.loads(read(MANIFEST))
        commands = [
            line[2:]
            for line in read(TRANSCRIPT).splitlines()
            if line.startswith("$ ") and not line.startswith("$ echo")
        ]
        self.assertEqual(record["invocation"]["commands"], commands)

    def test_readme_names_every_edit_the_manifest_declares(self) -> None:
        record = json.loads(read(MANIFEST))
        names = [entry["name"] for entry in record["output"]["transforms"]]
        self.assertEqual(names, ["replace-capture-root"])
        for name in names:
            self.assertIn("`%s`" % name, read(README))

    def test_transcript_carries_no_capture_path(self) -> None:
        text = read(TRANSCRIPT)
        self.assertIn("- Repo: `/work/demo-repo`", text)
        self.assertIn("not a git repository: /work/not-a-repo", text)
        # Spelled in pieces so that this file does not itself
        # contain the strings it looks for.
        users = "Use" + "rs"
        for leak in ("/%s/" % users, "/private/", "/var/folders", "/home/", "/tmp"):
            self.assertNotIn(leak, text)

    def test_transcript_shows_the_uncommitted_edit_the_example_describes(self) -> None:
        output = transcript_steps()["collect --repo demo-repo --recent 2"]
        dirty = output[output.index("## Dirty Files") :]
        self.assertEqual(dirty[3], " M greeter.py")
        self.assertIn("`greeter.py` is modified", read(EXAMPLE / "HANDOFF.md"))


class ReproductionTest(unittest.TestCase):
    def test_rebuilding_the_example_gives_the_recorded_commits(self) -> None:
        # The recorder's fixed author and dates make the two commit
        # ids the same on every machine.
        recorder = load(ROOT / "scripts" / "record_session.py", "record_session")
        with tempfile.TemporaryDirectory() as raw:
            base = Path(raw).resolve()
            repository = base / "demo-repo"
            recorder.build_repository(repository, base)
            log = subprocess.run(
                ["git", "-C", str(repository), "log", "--oneline", "--decorate", "-n2"],
                env=recorder.git_environment(base),
                capture_output=True,
                text=True,
                check=True,
            ).stdout.splitlines()
            status = subprocess.run(
                ["git", "-C", str(repository), "status", "--porcelain=v1"],
                env=recorder.git_environment(base),
                capture_output=True,
                text=True,
                check=True,
            ).stdout.splitlines()
        output = transcript_steps()["collect --repo demo-repo --recent 2"]
        recent = output[output.index("## Recent Commits") + 3 :][:2]
        self.assertEqual(log, recent)
        self.assertEqual(status, [" M greeter.py"])
        for line in recent:
            self.assertIn("`%s`" % line.split()[0], read(README))


class ExampleTest(unittest.TestCase):
    def test_example_says_it_is_synthetic(self) -> None:
        self.assertIn("This is synthetic example material.", read(ROOT / "examples" / "README.md"))

    def test_example_uses_the_default_paths(self) -> None:
        for path in DEFAULT_PATHS:
            self.assertTrue((EXAMPLE / path).exists(), path)
        state = json.loads(read(EXAMPLE / "handoff" / "state.json"))
        for agent in state["agents"]:
            if agent["detail_path"]:
                self.assertTrue((EXAMPLE / agent["detail_path"]).is_file())

    def test_example_snapshot_follows_the_template_headings(self) -> None:
        template = read(PACKAGE / "references" / "snapshot-template.md")
        headings = re.findall(r"^## .+$", template, flags=re.M)
        snapshot = re.findall(r"^## .+$", read(EXAMPLE / "HANDOFF.md"), flags=re.M)
        self.assertEqual(snapshot, headings)

    def test_example_log_entries_use_the_template_fields(self) -> None:
        template = read(PACKAGE / "references" / "log-entry-template.md")
        fields = re.findall(r"^- \*\*([^*]+):\*\*", template, flags=re.M)
        log = read(EXAMPLE / "HANDOFF.log.md")
        for entry in log.split("\n## ")[1:]:
            self.assertEqual(re.findall(r"^- \*\*([^*]+):\*\*", entry, flags=re.M), fields)


class DemoTest(unittest.TestCase):
    def test_images_agree_with_the_transcript(self) -> None:
        verifier = load(ROOT / "scripts" / "verify_demo.py", "verify_demo")
        generator = verifier.load_generator()
        self.assertEqual(verifier.problems_in(generator, read(TRANSCRIPT)), [])


class SocialPreviewTest(unittest.TestCase):
    def test_preview_is_the_size_github_expects(self) -> None:
        header = (ROOT / "assets" / "social-preview.png").read_bytes()[:24]
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", header[16:24]), (1280, 640))

    def test_stamp_binds_the_source_and_the_render(self) -> None:
        recorded = {}
        for line in read(ROOT / "assets" / "social-preview.sha256").splitlines():
            value, name = line.split()
            recorded[name] = value
        for name in ("social-preview.html", "social-preview.png"):
            self.assertEqual(recorded[name], sha256(ROOT / "assets" / name), name)

    def test_preview_source_carries_the_claim_and_transcript_rows(self) -> None:
        text = read(ROOT / "assets" / "social-preview.html")
        self.assertIn(CLAIM, " ".join(text.split()))
        transcript = set(read(TRANSCRIPT).splitlines())
        rows = re.findall(r"<div[^>]*>(\| [^<]*)</div>", text)
        self.assertEqual(len(rows), 3)
        for row in rows:
            self.assertIn(row, transcript)


class SupportFilesTest(unittest.TestCase):
    def test_license_is_mit(self) -> None:
        self.assertTrue(read(ROOT / "LICENSE").startswith("MIT License\n"))

    def test_security_names_this_repository_for_reports(self) -> None:
        self.assertIn(
            REPOSITORY + "/security/advisories/new",
            read(ROOT / "SECURITY.md"),
        )

    def test_contributing_names_the_check_command(self) -> None:
        self.assertIn("make check", read(ROOT / "CONTRIBUTING.md"))


if __name__ == "__main__":
    unittest.main()
