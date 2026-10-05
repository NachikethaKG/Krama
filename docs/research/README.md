# Research notes

Before each phase, each person works through their research list in [`docs/phases/`](../phases/README.md) and writes what they found here.
These notes are context for both of us and for the AI agents: start a phase by telling the agent to read the notes for it.

## The research loop

```
just research-prompt <phase> <you>     # e.g. just research-prompt 0 nachiketha  → prompt is on your clipboard
        ↓
paste into a NEW Gemini or Claude chat → research question by question
(the chat teaches, cites sources, and gives you small checks to run on your laptop)
        ↓
type HANDOFF → the chat outputs FILE blocks + a SUMMARY
        ↓
paste the whole handoff to the coding agent: "commit this research handoff"
        ↓
agent writes each FILE to docs/research/, one commit per note, on a docs/research branch → PR → the other person reviews
```

Tips:
- The prompt is generated from the current phase file, so regenerate it if the phase file changes.
- **Run the checks the chat gives you.** Research chats invent version numbers, limits and license terms with confidence. Anything still tagged `[unverified]` in the handoff should be treated as a guess.
- One chat per phase per person. If a chat gets long and confused, start a new one with the same prompt and paste your notes so far.
- The "Together" questions are for a call with the other person; the prompt helps you prepare for them, not answer them alone.

## File name

`phase-<n>-<who>-<topic>.md`, e.g. `phase-0-vishwas-gemini-structured-output.md`, `phase-1-nachiketha-captcha-detection.md`.
One topic per file, so the two of us never edit the same note.

## Template

```markdown
# <Topic>

- **Phase:** 0
- **Researched by:** Vishwas | Nachiketha
- **Question(s):** copy them from the phase file

## Findings
Short bullet points. Include versions and limits (e.g. "free tier: 10 requests/min").
Paste tiny code snippets you actually ran.

## Recommendation
What we should do, and why. If it changes architecture.md, say so (that needs an ADR).

## Open questions
Anything unresolved that the other person or the AI agent should know.

## Links
- docs, repos, articles you used
```

Research is done when the note answers every question in the phase's list for you, or says why one couldn't be answered.
