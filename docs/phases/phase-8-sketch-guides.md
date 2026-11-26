# Phase 8 (proposed) — Sketch guides for screens Krama can't open

> **Status: idea, not planned yet.** Proposed by Vishwas on 2026-11-26 and written down so Phase 8 planning starts
> from it. Nothing here is decided until the spike (below) has run and the decisions are asked in the Phase 6/7
> style. It starts only after the Phase 7 exit gate (#482) and v1.4. Epic: #499 · spike: #500.

## The problem
Krama makes tutorials by doing a task in its own browser. Many "how do I…" questions happen somewhere that browser
can't reach:

- a smart TV ("connect my TV to Wi‑Fi"), a set-top box, a router's physical buttons;
- a phone or tablet ("turn on hotspot on Android");
- desktop apps ("change the default printer in Windows", "export from Photoshop");
- anything behind hardware or a login Krama must never touch (banking apps; AGENTS.md §4).

Even the live sign-in (ADR 0012) can't help there: there is no web page to open. Today Krama can only refuse.

## The idea
For those tasks Krama **draws** the screens instead of recording them. It makes a simplified, approximate version of
each screen the user will see (white background, sketched boxes, icons and menu labels), and plays the usual
tutorial on top of it: cursor, highlight, captions and voice, step by step ("Settings → Network → Wi‑Fi → choose
your network").

### Why it fits Krama
- **Most of the pipeline can be reused.** The LLM writes each imagined screen as a tiny sketch-style HTML page.
  Krama's own agent then does the task on those pages in its browser, and the normal recorder, tutorial compiler
  and player (Phases 2 and 5) turn it into an interactive tutorial or a video. The new work is drawing the screens,
  not a new video system.
- **The sketch style is deliberate.** Drawn boxes instead of a copy of Samsung's, LG's or Apple's real interface
  avoid copying their designs and logos. They also tell the viewer at a glance: this is a guide, not a screenshot.

## Accuracy: the core rule
Krama's promise is **verified** tutorials. A sketch guide can't be verified: Krama never sees the real screen, and
menus differ by brand, model and software version. A confident video with a wrong menu path is worse than a text
answer. So:

1. **Ask first.** Brand, model, and software version if the user knows it ("Samsung QN90B, 2022", "Android 14 on
   a Pixel").
2. **Steps come from sources, not memory.** Web search finds the maker's official help page or manual for that model.
   The steps are taken from it and cited in the tutorial. The LLM draws a path someone documented; it doesn't
   invent one. Search also catches redesigns: when the maker's current page describes a new menu layout, that's the
   one drawn.
3. **Approximate is fine; say so.** The layout drawn is the best guess at *where* things are, such as "Network is
   the third item in the Settings list". It won't be perfect, and that's OK: these layouts change slowly, and an
   approximate map still gets people there. Every guide says so plainly, for example:
   > **Your screen should look roughly like this.** It's a sketch based on [Samsung's guide for the QN90B](...),
   > not a picture of your TV. Names and positions may differ a little.
4. **Show how sure Krama is, with reasons, not a fake percentage.** A confidence level per guide, and per step
   where it differs:
   - **High:** the official guide for this exact model and software version.
   - **Medium:** the official guide for the same brand, but another model or version.
   - **Low:** no official guide found; the path comes from community answers or general knowledge.

   Each level names its source, so the user can check it.
5. **Kept apart from verified tutorials.** A sketch guide never gets the "verified" badge, lives under its own
   label, and is never mixed into a verified workflow.

## Open questions (for the spike and the decisions)
- **Quality:** can Gemini turn a real help page into 3–4 sketch screens good enough that someone can follow them on
  a real device? This is the question the spike must answer first.
- **Drawing:** HTML pages the agent then "uses" (reuses the recorder), or SVG scenes fed straight to the compiler?
- **Sources:** which search does Krama use on the free tier, and how does it rank official pages above forums?
- **Free tier:** a guide costs a search, a few LLM calls to draw screens, and the step agent's calls. Does that fit
  the about 3 tasks a day the free tier allows (finding from #494)?
- **Safety:** a sketch guide is still steps a user follows by hand on a real device. Risky steps (factory reset,
  deleting data) need the same warnings as verified ones. The sensitive-site rule (banking, payments, government
  identity, health) applies to sketch guides too.
- **Product:** where in the UI does Krama offer a sketch guide? Probably when it can't open the target, as the
  answer to today's refusal.

## Proposed first step: a spike
Three tasks, each on a device Krama can't reach. For each one: find the official guide, draw 3–4 sketch screens,
and make the tutorial. Then judge whether each guide is followable, using a real device where we have one, and
whether its confidence label was right.

Example tasks:
- "Connect a Samsung smart TV (2022) to Wi‑Fi."
- "Turn on the mobile hotspot on Android 14."
- "Change the default printer in Windows 11."

Write the result up as `docs/research/phase-8-*-sketch-guides-spike.md`, then propose the decisions.
