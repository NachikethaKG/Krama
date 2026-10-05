# Phase 2: Interactive tutorial

**Goal:** turn a stored Verified Workflow into an interactive tutorial on the real UI: replay, cursor, highlights, zoom, captions, narration. Someone who has never used Gitea can follow it.

**Release tag:** `v0.2`

**Who builds what**
- **Vishwas:** better instruction text, exact coordinates, re-verification, a text-guide output, more Gitea tasks.
- **Nachiketha:** recording/timing alignment (`observer/`), the tutorial compiler and player, benchmark reports.

---

## Research before starting

> **Research chat prompts:** copy yours from [#68 (Vishwas)](https://github.com/NachikethaKG/Krama/issues/68) or [#69 (Nachiketha)](https://github.com/NachikethaKG/Krama/issues/69), or run `just research-prompt 2 <name>`. Together questions: [#70](https://github.com/NachikethaKG/Krama/issues/70). How it works: [`docs/research/`](../research/README.md).

**Vishwas**
- **Instruction text:** what makes a good UI instruction? (Imperative, quote the exact label, say where on screen: "Click **New Repository** in the top-right `+` menu.") Write a prompt and compare outputs.
- **Local model test:** run the same instruction-text prompt on your RTX 4050 with Ollama (Llama 3.1 8B / Qwen 2.5 7B) vs Gemini Flash. Is the local output good enough for this one cheap text job? (This decides whether `LLM_PROVIDER_TEXT=ollama` is worth keeping.)
- **Coordinates:** page vs viewport coordinates, scroll offsets, device pixel ratio. How do you store a bbox so it lines up with the replay later?
- **Re-verification:** replay a stored workflow headlessly using stored locators, without the planner. What should happen when one step's locator no longer matches?
- **More Gitea tasks:** create an issue, create a branch, add a file, change repo settings. Which are stable, which need extra setup?

**Nachiketha**
- **Study the best tutorial tools:** Arcade, Scribe, Supademo, Tango, Guidde, Screen Studio. What makes them easy to follow (zoom timing, highlight style, pacing, step text length)? Bring screenshots.
- **Cursor motion:** easing curves and bezier paths that look natural; auto-zoom like Screen Studio; respecting `prefers-reduced-motion`.
- **Timing alignment:** how do rrweb event timestamps relate to Playwright action times? How do you map a step's `start_ms`/`end_ms` onto the recording?
- **Narration:** Web Speech API voices in Chrome and Edge on Windows. Quality, offline availability, and how to sync captions to speech (`onboundary` events).
- **Player accessibility:** keyboard controls, captions, focus handling, screen-reader labels (WCAG 2.2 basics for media players).

**Together**
- Design `tutorial-spec.schema.json`: scenes, cursor path, highlights, zooms, captions, timings. Look at how `rrweb-player` and Remotion compositions consume time, since Phase 5 reuses the same spec.

---

## Sprint 2.1: compiler

**Together (contract PR):** `tutorial-spec.schema.json` v1 + a fixture.

| Vishwas | Nachiketha |
|---|---|
| `agent/`: store each target's bbox in page coordinates, plus viewport size and scroll | `observer/`: record rrweb on every run and align its timestamps with each step's `timing` |
| `planner/`: instruction-text quality pass (rewrite into human-friendly wording) | `packages/tutorial-compiler`: pure TS `Workflow → TutorialSpec` (scenes, bezier cursor paths, click ripples, highlights, zoom regions, caption timings) |
| ADR: local model vs Gemini for text jobs (from the research) | Compiler snapshot tests on fixtures |

## Sprint 2.2: player

| Vishwas | Nachiketha |
|---|---|
| `api/` + `runs/`: `POST /workflows/{id}/reverify` (headless replay of stored steps) | Frontend: tutorial player: play/pause, next/previous step, replay a step, zoom, step list, captions, copyable text |
| Gitea reset between benchmark runs; 4 more Gitea tasks in `benchmarks/tasks/` | Frontend: Web Speech narration; mobile layout; keyboard and screen-reader support |
| `api/`: text-guide output (`GET /workflows/{id}/guide.md`, numbered steps with screenshots) | `benchmarks/`: HTML/Markdown report across all tasks (success rate, verifier accuracy, latency) |

## Exit criteria
- A person who has never used Gitea follows a generated tutorial and completes the task.
- 5 Gitea workflows pass the benchmark at ≥ 80%.
- The player works with keyboard only, and with narration off (captions only).
- Demoed on Nachiketha's laptop.
