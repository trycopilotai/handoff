#!/usr/bin/env python3
"""Render an agent invocation's raw JSON-lines output as text.

    python3 scripts/render_invocation.py --client claude-code \
        --prompt prompt.txt --root <fixture> --plugin-root <clone> \
        --home <home> --hostname <name> raw.jsonl > transcript.txt

Writes the prompt, every tool call (its name, and its arguments
re-serialised as JSON with sorted keys, each argument string cut
at LIMIT characters), each call's status where the raw output
records it, and the final message with the same replacements
applied. The replacements, in this order, each applied to a
whole path prefix and never inside a longer name: an
--isolation-root becomes /iso, each --plugin-root (the
directory the client loaded the skill from) /plugin, the
fixture's absolute path /work, a client scratch directory
/private/tmp/claude-<uid>/<slug> /scratch, the home directory
~, and each --hostname host. They run on each whole string
before it is cut, so a cut never leaves part of a path they
would replace. Standard library only; output depends only on
the inputs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

LIMIT = 300
# A path or name ends at a separator, a quote, whitespace or the end.
END = r"(?=[/\\\s\"'`)]|$)"
SCRATCH = re.compile(r"(?<![\w.-])/private/tmp/claude-[0-9]+/[^/\s\"'`]+" + END)


def prefix(path: str, replacement: str):
    """Replace `path` where it is a whole path prefix."""
    pattern = re.compile(r"(?<![\w.-])" + re.escape(path.rstrip("/")) + END)
    return lambda text: pattern.sub(lambda match: replacement, text)


def hostname(name: str):
    pattern = re.compile(r"(?<![\w.-])" + re.escape(name) + r"(?![\w-]|\.\w)")
    return lambda text: pattern.sub(lambda match: "host", text)


def transforms(options):
    steps = []
    if options.isolation_root:
        steps.append(prefix(options.isolation_root, "/iso"))
    steps += [prefix(path, "/plugin") for path in options.plugin_root]
    steps.append(prefix(options.root, "/work"))
    steps.append(lambda text: SCRATCH.sub(lambda match: "/scratch", text))
    steps.append(prefix(options.home, "~"))
    steps += [hostname(name) for name in sorted(options.hostname, key=len, reverse=True)]

    def apply(text: str) -> str:
        for step in steps:
            text = step(text)
        return text

    return apply


def cut(value, apply):
    if isinstance(value, str):
        value = apply(value)
        if len(value) > LIMIT:
            return value[:LIMIT] + "...[%d more characters]" % (len(value) - LIMIT)
        return value
    if isinstance(value, dict):
        return {key: cut(item, apply) for key, item in value.items()}
    if isinstance(value, list):
        return [cut(item, apply) for item in value]
    return value


def claude_code(events, arguments):
    calls, final, model, version = [], None, None, None
    results = {}
    for event in events:
        kind = event.get("type")
        if kind == "system" and event.get("subtype") == "init":
            model, version = event.get("model"), event.get("claude_code_version")
        elif kind in ("assistant", "user"):
            content = event["message"].get("content")
            for block in content if isinstance(content, list) else []:
                if block.get("type") == "tool_use":
                    calls.append((block["id"], block["name"], block.get("input")))
                elif block.get("type") == "tool_result":
                    results[block["tool_use_id"]] = (
                        "error" if block.get("is_error") else "ok"
                    )
        elif kind == "result":
            final = event.get("result")
    header = ["client: Claude Code %s" % version, "model: %s" % model]
    lines = [
        "%s %s\n  status: %s" % (name, arguments(given), results.get(ident, "unknown"))
        for ident, name, given in calls
    ]
    return header, lines, final


def codex(events, arguments):
    lines, final = [], None
    for event in events:
        if event.get("type") != "item.completed":
            continue
        item = event["item"]
        if item.get("type") == "command_execution":
            lines.append(
                "command_execution %s\n  status: %s, exit %s"
                % (arguments({"command": item["command"]}), item.get("status"), item.get("exit_code"))
            )
        elif item.get("type") == "agent_message":
            final = item["text"]
        elif item.get("type") not in ("reasoning",):
            lines.append("%s %s" % (item.get("type"), arguments(item)))
    return ["client: Codex"], lines, final


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", choices=("claude-code", "codex"), required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--isolation-root")
    parser.add_argument("--plugin-root", action="append", default=[])
    parser.add_argument("--home", required=True)
    parser.add_argument("--hostname", action="append", default=[])
    parser.add_argument("raw")
    options = parser.parse_args(argv)
    apply = transforms(options)
    with open(options.raw, encoding="utf-8") as stream:
        events = [json.loads(line) for line in stream if line.strip()]
    with open(options.prompt, encoding="utf-8") as stream:
        prompt = stream.read().rstrip("\n")

    def arguments(value) -> str:
        return json.dumps(cut(value, apply), ensure_ascii=False, sort_keys=True)

    render = claude_code if options.client == "claude-code" else codex
    header, lines, final = render(events, arguments)
    text = "\n".join(
        header
        + ["", "## prompt", "", apply(prompt), "", "## tool calls", ""]
        + ["%d. %s" % (number, line) for number, line in enumerate(lines, 1)]
        + ["", "## final message", "", apply(final) if final is not None else "(none)", ""]
    )
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
