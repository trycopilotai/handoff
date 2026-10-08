#!/usr/bin/env python3
"""Generate the terminal demo and its static poster.

Both images are reconstructed from the recorded session in
evidence/transcripts/collector-session.txt. Every line of
terminal text they show is copied from that file, so the
demo cannot show a line the transcript lacks. The other text
is the image's title and description and a footer naming
the transcript. Of the Markdown report, only the summary
bullets and the agent ownership table are shown; of the
other commands, every non-empty output line is shown.

    python3 scripts/generate_demo.py            # write both
    python3 scripts/generate_demo.py --check    # compare only

The demo reveals the session in steps and loops. Each step
stays on screen until the fade that ends the loop, so a
later frame always contains every earlier one. The poster is the last
frame with no animation, for a reader who asked for reduced
motion.
"""

from __future__ import annotations

import argparse
import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT = ROOT / "evidence" / "transcripts" / "collector-session.txt"
DEMO = ROOT / "assets" / "demo.svg"
POSTER = ROOT / "assets" / "poster.svg"
SOURCE_LABEL = "Reconstructed from evidence/transcripts/collector-session.txt"

WIDTH = 1280
HEIGHT = 720
MARGIN_X = 40
FIRST_BASELINE = 108
LINE_HEIGHT = 26
STEP_GAP = 14
FONT_SIZE = 16
# A monospace glyph is about 0.6 em wide. The verifier uses
# the same figure to prove the longest line fits the canvas.
GLYPH_WIDTH = 0.6 * FONT_SIZE
LABEL_FONT_SIZE = 15

BACKGROUND = "#101418"
TEXT = "#f7fbff"
MUTED = "#a7bac5"
WARN = "#ffd166"
GOOD = "#55d6be"
CHROME = ("#ff6b6b", "#ffd166", "#55d6be")

LOOP_SECONDS = 12
# Percent of the loop at which each step appears. Every step
# holds until HOLD_UNTIL, fades out, and the loop restarts.
REVEAL_AT = (6, 40, 64)
FADE_IN = 4
HOLD_UNTIL = 94

COMMAND_PREFIX = "$ collect() {"
STEP_COUNT = 3
REPORT_TITLE = "# Handoff State Collection"
# Lines of the Markdown report that the demo shows.
REPORT_LINES = ("- ", "| ")


def steps_from_transcript(transcript: str) -> tuple[str, list[list[str]]]:
    """The shell function, then one block per command.

    A block is the command line, the lines of its output the demo
    shows, and the exit status line. For a Markdown report those
    are the summary bullets and the table rows; for any other
    output, every non-empty line.
    """
    lines = transcript.splitlines()
    if not lines or not lines[0].startswith(COMMAND_PREFIX):
        raise ValueError("the transcript does not start with the function")
    header = lines[0]
    steps: list[list[str]] = []
    report = False
    for line in lines[1:]:
        if line.startswith('$ echo "exit status'):
            continue
        if line.startswith("$ "):
            steps.append([line])
            report = False
            continue
        if not steps:
            raise ValueError("output appears before the first command")
        if line == REPORT_TITLE and len(steps[-1]) == 1:
            report = True
            continue
        if line == "":
            continue
        if report and not line.startswith(REPORT_LINES) and not line.startswith("exit status: "):
            continue
        steps[-1].append(line)
    if len(steps) != STEP_COUNT:
        raise ValueError(
            "expected %d commands, found %d" % (STEP_COUNT, len(steps))
        )
    for block in steps:
        if not block[-1].startswith("exit status: "):
            raise ValueError("a command has no exit status: %s" % block[0])
    return header, steps


def line_colour(line: str) -> str:
    stripped = line.strip()
    if stripped.startswith("$ "):
        return TEXT
    if stripped.startswith("exit status: 0"):
        return GOOD
    if stripped.startswith("exit status: "):
        return WARN
    if stripped.startswith(("--state-file must", "not a git repository", "fatal:")):
        return WARN
    return TEXT


def text_element(line: str, baseline: int) -> str:
    return (
        '    <text x="%d" y="%d" fill="%s" xml:space="preserve">%s</text>'
        % (MARGIN_X, baseline, line_colour(line), html.escape(line))
    )


def layout(command: str, steps: list[list[str]]) -> tuple[list[str], int]:
    """SVG fragments for the command and each step, and the last baseline."""
    fragments = [text_element(command, FIRST_BASELINE)]
    baseline = FIRST_BASELINE
    for index, block in enumerate(steps):
        baseline += STEP_GAP
        fragments.append('    <g class="step-%d">' % (index + 1))
        for line in block:
            baseline += LINE_HEIGHT
            fragments.append("  " + text_element(line, baseline))
        fragments.append("    </g>")
    return fragments, baseline


def animation_css() -> str:
    rules = []
    for index, reveal in enumerate(REVEAL_AT):
        number = index + 1
        rules.append(
            "    .step-%d {\n"
            "      opacity: 0;\n"
            "      animation: reveal-%d %ds infinite;\n"
            "    }" % (number, number, LOOP_SECONDS)
        )
        rules.append(
            "    @keyframes reveal-%d {\n"
            "      0%%, %d%% { opacity: 0; }\n"
            "      %d%%, %d%% { opacity: 1; }\n"
            "      100%% { opacity: 0; }\n"
            "    }" % (number, reveal, reveal + FADE_IN, HOLD_UNTIL)
        )
    selectors = ", ".join(".step-%d" % (i + 1) for i in range(len(REVEAL_AT)))
    rules.append(
        "    @media (prefers-reduced-motion: reduce) {\n"
        "      %s {\n"
        "        opacity: 1;\n"
        "        animation: none;\n"
        "      }\n"
        "    }" % selectors
    )
    return "\n".join(rules)


def render(transcript: str, animated: bool) -> str:
    command, steps = steps_from_transcript(transcript)
    fragments, last_baseline = layout(command, steps)
    label_baseline = HEIGHT - 28
    if last_baseline + LINE_HEIGHT > label_baseline - LABEL_FONT_SIZE:
        raise ValueError("the session does not fit the canvas")
    if animated:
        title = "Animated handoff collector session"
        style = "  <style>\n%s\n  </style>\n" % animation_css()
    else:
        title = "handoff collector session"
        style = ""
    description = (
        "A terminal runs the handoff collector on a synthetic repository "
        "and prints one ownership table row per agent, is refused a state "
        "file outside the repository with exit status 2, and is told a "
        "plain directory is not a git repository with exit status 1."
    )
    chrome = "\n".join(
        '  <circle cx="%d" cy="44" r="9" fill="%s" />' % (40 + 30 * i, colour)
        for i, colour in enumerate(CHROME)
    )
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
        'viewBox="0 0 %d %d" role="img" aria-labelledby="title description">\n'
        '  <title id="title">%s</title>\n'
        '  <desc id="description">%s</desc>\n'
        "%s"
        '  <rect width="%d" height="%d" rx="24" fill="%s" />\n'
        "%s\n"
        '  <g font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        'font-size="%d">\n'
        "%s\n"
        "  </g>\n"
        '  <text x="%d" y="%d" fill="%s" '
        'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
        'font-size="%d">%s</text>\n'
        "</svg>\n"
        % (
            WIDTH,
            HEIGHT,
            WIDTH,
            HEIGHT,
            title,
            description,
            style,
            WIDTH,
            HEIGHT,
            BACKGROUND,
            chrome,
            FONT_SIZE,
            "\n".join(fragments),
            MARGIN_X,
            label_baseline,
            MUTED,
            LABEL_FONT_SIZE,
            SOURCE_LABEL,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if either committed image differs from a fresh render",
    )
    arguments = parser.parse_args(argv)
    transcript = TRANSCRIPT.read_text(encoding="utf-8")
    outputs = (
        (DEMO, render(transcript, animated=True)),
        (POSTER, render(transcript, animated=False)),
    )
    if arguments.check:
        stale = [
            path.name
            for path, text in outputs
            if not path.exists() or path.read_text(encoding="utf-8") != text
        ]
        if stale:
            print("stale: %s. Run scripts/generate_demo.py." % ", ".join(stale))
            return 1
        print("demo.svg and poster.svg match the transcript")
        return 0
    for path, text in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        print("wrote %s" % path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
