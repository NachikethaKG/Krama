# 0009 — Tutorials in other languages: translated with UI labels kept as tokens, narrated only with licensed voices

- **Status:** accepted
- **Deciders:** Vishwas (2026-11-19, decisions L1–L11). Nachiketha is away; the export module and the video
  exporter changes (#428, #429) are in his area, so he should read this when he is back.
- **Issue:** #420 · Research: [`phase-6-nachiketha-multiple-languages.md`](../research/phase-6-nachiketha-multiple-languages.md),
  [`phase-6-vishwas-indic-parler-tts.md`](../research/phase-6-vishwas-indic-parler-tts.md); decisions L1–L11 in
  [`phase-6-decisions-alignment.md`](../research/phase-6-decisions-alignment.md). Updates
  [ADR 0004](0004-piper-voice-and-license.md).

## Context
Tutorials are written in English by the planner. A step quotes the site's own labels (Click “New repository”):
those are what the learner must find on the page, so they must stay exactly as the site shows them, in the site's
language, while the sentence around them is translated. ADR 0004 allowed one narration voice, `ljspeech` (public
domain), and ruled out lessac-derived, non-commercial and research-only voices.

The research translated 17 step texts into Hindi, Kannada, German and Spanish with Gemini, swapping each quoted
label for a token first: all 68 kept every label byte for byte, and a label written as an injection never reached
the model. Without tokens, labels were sometimes translated. Gemini was slow and flaky on the free tier that day
(3 requests and 31–66 s per batch), so translation can't sit in a request path.

## Decision
1. **Languages:** tutorials in English (original), Hindi, Kannada, German, Spanish and French (`Language` in the
   contract). The app's own UI language is separate (#423).
2. **Translation (L4–L6):** one LLM request per tutorial. Every UI label (each quoted label, and for older texts
   the step's target name) becomes a token `[[Qn]]`; the reply must use every token exactly once, then the labels
   go back byte for byte. A step whose tokens don't come back keeps its English text (`translated: false`), never
   a half-translated one. Quote marks around labels stay the original curly quotes.
3. **When (L5):** on first request of a (workflow version, language), in the background
   (`GET /workflows/{id}/translations/{language}` answers 202 until ready); each text is cached by (sha256,
   language, prompt version), so a new version only translates what changed. A failure is reported once and
   retried on the next request. Exports wait for the translation.
4. **Voices (L7), updating ADR 0004:** narration only with a voice that passes ADR 0004's rule. German
   `de_DE-thorsten-medium` (CC0), Spanish `es_ES-davefx-medium` (CC0), French `fr_FR-siwis-medium` (CC BY 4.0;
   credited in the video's outro). English stays `ljspeech`. **Hindi and Kannada get captions only**: a silent
   track sized like speech, so scenes, captions and chapters work unchanged.
5. **Indic narration later (L8):** Indic Parler-TTS (Apache-2.0) was measured on this CPU-only laptop
   (see its research note); it is adopted only if that note's conditions are met.
6. **Video (L9):** bundled Noto Sans Devanagari and Kannada (SIL OFL 1.1) for captions and cards, and the
   video's fixed strings (chapters, intro, outro) per language.
7. **Tests (L11):** fake translators and fake LLM replies in CI; real Gemini only at checkpoints.

## Alternatives considered
- **Translate the labels too.** The learner would look for words the site doesn't show. Rejected.
- **Ask the model to keep quoted text.** It sometimes didn't; tokens make it checkable. Rejected.
- **Translate on save, every language.** Spends quota on languages nobody opens. Rejected.
- **Reviewed per-language templates instead of an LLM.** The deterministic step text has only ~16 sentence
  shapes, so this is cheaper and exact later, but each language needs a reviewer first. Kept for later.
- **Ship the available Hindi voices.** They are non-commercial (CC BY-NC-SA) or lessac-derived. Rejected by
  ADR 0004's rule.

## Consequences
- Easier: one export pipeline for every language; translations are cheap after the first request.
- Harder: Hindi and Kannada text needs a native reader before release; translations use Gemini quota (one request
  per tutorial and language); three more voice models to download (`just backend tts-setup`); the French outro
  carries an attribution line.
