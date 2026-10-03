# Research notes

Before each phase, each person works through their research list in [`docs/phases/`](../phases/README.md) and writes what they found here.
These notes are context for both of us and for the AI agents: start a phase by telling the agent to read the notes for it.

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
