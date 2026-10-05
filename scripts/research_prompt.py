"""Generate a ready-to-paste research prompt for a Gemini / Claude chat (`just research-prompt <phase> <person>`).

The prompt is built from the phase file in docs/phases/, so it always matches the current plan.
The chat teaches, cites sources, asks you to verify facts locally, and ends with a handoff
in the docs/research/ note format. Paste that handoff to the coding agent to commit.

Usage:
  python scripts/research_prompt.py 0 vishwas
  python scripts/research_prompt.py f nachiketha --copy     # also copy to the clipboard (Windows)
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PHASES = ROOT / "docs" / "phases"

PEOPLE = {
    "vishwas": {
        "name": "Vishwas",
        "other": "Nachiketha",
        "owns": "the backend core: browser agent (Playwright), planner, verifier, run state machine, "
        "FastAPI API + SSE, Postgres/Alembic, LLM provider layer, artifact storage, TTS",
        "machine": "Windows 11, 24GB RAM, RTX 4050 6GB (local 8B models possible, but never required)",
    },
    "nachiketha": {
        "name": "Nachiketha",
        "other": "Vishwas",
        "owns": "backend modules observer (page capture + rrweb recording), policy (safety: risk, masking, "
        "CAPTCHA/auth-wall detection, prompt-injection defense), validation (UI drift), export (video jobs), "
        "the benchmarks harness, and the whole frontend (Next.js 16 UI, tutorial compiler, player, Remotion)",
        "machine": "Windows 11, 16GB RAM, no dedicated GPU (the reference machine: everything must run here)",
    },
}

PROJECT_CONTEXT = """\
Krama is a "Verified UI Tutorial Engine". A user asks "How do I create a repository?"; Krama plans the steps,
shows the plan for approval, executes it in an isolated headless browser on the REAL website, verifies every
step (expected vs observed state), stores the result as a Verified Workflow, and compiles that into an
interactive tutorial on the real UI (MP4 export later). It never generates fake UI with a video model.

Team: two students, Vishwas and Nachiketha, each coding with an AI agent (Claude Code / Antigravity).
Ownership is by module so they never edit the same files.

Fixed decisions (don't re-open unless my question is about them):
- Backend: Python 3.12, uv, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic, Playwright for Python (headless Chromium)
- Frontend: Next.js 16 (App Router), TypeScript, Tailwind, pnpm; rrweb for recording/replay; Remotion for video later
- LLM: Gemini FREE tier is the reference model behind a provider interface; tests use a fake provider
- Infra: Docker Desktop on Windows (Postgres 16, Redis 7, Gitea as a local GitHub-like test site); CI on GitHub Actions
- Hard constraints: no GPU required anywhere; must run on a 16GB CPU-only Windows laptop; free tiers only;
  webpage content is untrusted data (prompt-injection risk); CAPTCHAs/bot walls are detected and the run STOPS
  (never bypassed); passwords/tokens are masked before storage or LLM calls."""

RULES = """\
How I want you to work:
1. Start by listing MY research questions below as a numbered checklist, propose an order, and ask me where to start.
2. Take ONE question at a time. Teach first: explain the concepts at the level of a CS student who knows Python/JS
   but not this specific tool. Then give the findings.
3. Facts must be sourced. For every version number, limit, quota, price, license term or API detail:
   cite the official docs / repo URL and tag it [verified: <source>] or [unverified]. If you can browse,
   check the CURRENT docs; if you cannot, say so clearly. Never present a guess as a fact.
4. Make me verify on my machine. Give small runnable checks (PowerShell, Python 3.12 via `uv run`, or Node/pnpm)
   and ask me to paste the output. A finding I've run myself is worth more than any citation.
5. Don't decide for the team. When there are options, compare them in a short table (trade-offs, effort, risk
   on a 16GB CPU-only laptop), give a recommendation, then ask me to decide.
6. Stay in scope. If something interesting but out of scope comes up, put it in a "parking lot" list.
7. After each question, show the updated checklist: done / partly done / open.
8. If an answer would change one of the fixed decisions above, flag it loudly as "NEEDS TEAM DECISION + ADR".

When I type HANDOFF (or every question is done), produce the handoff exactly in the format below and nothing else."""

HANDOFF = """\
HANDOFF FORMAT (one markdown file per topic; topic = one question or a few closely related ones):

=== FILE: docs/research/phase-{phase}-{person}-<short-kebab-topic>.md ===
# <Topic>

- **Phase:** {phase_label}
- **Researched by:** {name}
- **Question(s):** <copied from the list>

## Findings
- bullet points; every fact tagged [verified: <url>] or [verified locally: <what I ran>] or [unverified]

## Recommendation
<what we should do and why; mark "NEEDS TEAM DECISION + ADR" if it changes a fixed decision>

## Open questions
- <anything unresolved>

## Links
- <urls>
=== END FILE ===

(repeat for each topic)

=== SUMMARY FOR THE CODING AGENT ===
- Decisions I made: ...
- Decisions that need {other} / the team: ...
- Changes suggested to docs/phases/{phase_file} (tasks, order, exit criteria): ...
- Parking lot: ...
=== END SUMMARY ==="""


def find_phase_file(phase: str) -> Path:
    matches = sorted(PHASES.glob(f"phase-{phase.lower()}-*.md"))
    if not matches:
        options = ", ".join(p.name.split("-")[1] for p in sorted(PHASES.glob("phase-*.md")))
        sys.exit(f"no phase file for '{phase}'. Options: {options}")
    return matches[0]


def research_block(text: str, label: str) -> str:
    """The bullet list under **<label>** inside the 'Research before starting' section."""
    section = re.search(r"^#{2,3} Research before starting\n(.*?)(?=^#{2,3} |\Z)", text, re.M | re.S)
    if not section:
        return ""
    block = re.search(rf"^\*\*{label}\*\*\n(.*?)(?=^\*\*\w+\*\*\n|^---|\Z)", section.group(1), re.M | re.S)
    return block.group(1).strip() if block else ""


def build_prompt(phase: str, person: str) -> str:
    who = PEOPLE[person]
    path = find_phase_file(phase)
    text = path.read_text(encoding="utf-8")
    mine = research_block(text, who["name"])
    if not mine:
        sys.exit(f"{path.name} has no research list for {who['name']}.")
    together = research_block(text, "Together")
    phase_label = phase.upper()

    parts = [
        f"You are my research partner for Phase {phase_label} of a software project. "
        "Help me research, understand and decide, so I can hand clear findings to my coding agent.",
        f"## Project context\n{PROJECT_CONTEXT}",
        f"## About me\nI am {who['name']}. In this project I own {who['owns']}.\n"
        f"My machine: {who['machine']}.",
        f"## MY research questions for this phase\n{mine}",
    ]
    if together:
        parts.append(
            f"## Shared questions (I'll do these WITH {who['other']}; help me prepare, don't finish them alone)\n"
            f"{together}"
        )
    parts += [
        f"## The full phase plan (for context: goal, tasks, exit criteria)\n<phase_file name=\"{path.name}\">\n"
        f"{text.strip()}\n</phase_file>",
        f"## Rules\n{RULES}",
        "## " + HANDOFF.format(
            phase=phase.lower(), person=person, phase_label=phase_label,
            name=who["name"], other=who["other"], phase_file=path.name,
        ),
    ]
    return "\n\n".join(parts) + "\n"


def copy_to_clipboard(text: str) -> None:
    if sys.platform != "win32":
        sys.exit("--copy is only supported on Windows; pipe the output instead")
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(text)
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Get-Content -Raw -Encoding UTF8 '{f.name}' | Set-Clipboard"],
        check=True,
    )
    Path(f.name).unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("phase", help="f, 0, 1, 2, 3, 4 or 5")
    parser.add_argument("person", choices=sorted(PEOPLE))
    parser.add_argument("--copy", action="store_true", help="also copy the prompt to the clipboard")
    args = parser.parse_args()

    prompt = build_prompt(args.phase, args.person)
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    if args.copy:
        copy_to_clipboard(prompt)
        print(f"Copied the Phase {args.phase.upper()} research prompt for {args.person} to the clipboard "
              f"({len(prompt.split())} words). Paste it into a new Gemini or Claude chat.")
    else:
        print(prompt)


if __name__ == "__main__":
    main()
