# Narration via Web Speech API and Caption Synchronization

- **Phase:** 2
- **Researched by:** Nachiketha
- **Question(s):** Narration: Web Speech API voices in Chrome and Edge on Windows. Quality, offline availability, and how to sync captions to speech (`onboundary` events).

## Findings

### 1. Voice Quality and Availability on Windows 11 Chrome & Edge

The Web Speech API (`window.speechSynthesis`) provides native client-side speech generation without requiring cloud API calls, latency penalties, or server-side audio storage [verified: MDN Web Speech API, verified locally].

- **Online Voices (Tier 1 Quality):**
  - In Microsoft Edge and Google Chrome on Windows 11, the browser exposes neural **Microsoft Natural Online** voices:
    - `Microsoft Jenny Online (Natural) - English (United States)`
    - `Microsoft Guy Online (Natural) - English (United States)`
    - `Microsoft Aria Online (Natural) - English (United States)`
  - Quality is near-human with natural prosody, breathing pauses, and proper intonation for technical UI terms [verified locally].
  - *Dependency:* Requires active internet connection; provided natively by the browser platform at zero cost.
- **Offline Voices (Tier 2 Fallback):**
  - When offline or in restricted network environments, Windows 11 provides local SAPI5 speech synthesis engines:
    - `Microsoft David - English (United States)` (local desktop voice)
    - `Microsoft Zira - English (United States)` (local desktop voice)
    - `Microsoft Mark - English (United States)` (local mobile voice)
  - Quality sounds slightly robotic but has zero network dependency, zero latency, and runs entirely on a 16GB CPU-only laptop [verified locally].
- **Voice Selection Algorithm:**
  ```typescript
  function selectOptimalVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
    // 1. Prioritize Microsoft Natural Online English voices
    const natural = voices.find(
      (v) => v.lang.startsWith("en") && v.name.includes("Natural") && v.name.includes("Microsoft")
    );
    if (natural) return natural;

    // 2. Fall back to standard Google / Microsoft English voices
    const standard = voices.find((v) => v.lang.startsWith("en") && !v.localService);
    if (standard) return standard;

    // 3. Fall back to local offline voices (David, Zira)
    const local = voices.find((v) => v.lang.startsWith("en") && v.localService);
    return local || voices[0] || null;
  }
  ```

### 2. Caption Synchronization via `onboundary`

Synchronizing closed captions word-by-word with spoken audio is essential for accessibility and instructional clarity [verified: W3C Web Speech API, verified locally]:

- **Boundary Event Mechanics:**
  The `SpeechSynthesisUtterance` interface exposes the `onboundary` event:
  ```typescript
  const utterance = new SpeechSynthesisUtterance(instructionText);
  utterance.voice = selectedVoice;
  utterance.rate = 1.0; // standard speaking rate ~140-160 wpm

  utterance.onboundary = (event: SpeechSynthesisEvent) => {
    if (event.name === "word") {
      const charIndex = event.charIndex; // Character index in utterance string
      const wordLength = event.charLength || findNextWordLength(instructionText, charIndex);
      highlightActiveWord(charIndex, wordLength);
    }
  };
  ```
- **Word-Level Highlighting:**
  The caption UI splits the instruction text into tokens. As `onboundary` triggers with `charIndex`, the player highlights the currently spoken word with an accent badge or glowing underline, allowing users to read along in lockstep with the voice [verified locally].

### 3. Fallback for Erratic Environments

In certain Linux Chromium distributions or headless environments, `onboundary` events can fail to fire or fire all at once upon completion [verified locally]:

- **Heuristic Duration Fallback Model:**
  When `onboundary` does not trigger within the first 300 ms of playback, fallback to a deterministic time-based word progression model:
  $$\text{duration}_{\text{word}} = \max\left(220\text{ ms}, \text{length} \times 45\text{ ms}\right)$$
  - Punctuation delays added:
    - Comma `,` or semicolon `;`: $+150\text{ ms}$
    - Period `.`, exclamation `!`, or question `?`: $+350\text{ ms}$
  This ensures smooth progressive caption advancement even when browser speech events are disabled or simulated.

### 4. Audio Control & Safety

- Audio must never autoplay unprompted (violates browser autoplay policies and causes audio shock).
- Audio is muted by default or enabled only upon user activation of "Narrate Tutorial".
- Global mute toggle (`M` shortcut) cancels active speech immediately via `window.speechSynthesis.cancel()`.

## Recommendation

1. Adopt the Web Speech API in `@krama/player` for tutorial narration:
   - Zero external cloud TTS API costs or quotas.
   - High-quality Natural voice priority with automatic local SAPI5 offline fallback.
2. Implement word-level caption synchronization using `onboundary`, backed by the heuristic reading-rate fallback.
3. Include speech synthesis configuration in `packages/tutorial-compiler` (voice preferences, pacing rate, pitch).
[No ADR required: conforms to Phase 2 roadmap].

## Open questions

- Should the player cache pre-recorded audio files for export formats (e.g. MP4 / WebM video export in Phase 5)? (Yes: Web Speech is live in-browser; Phase 5 will need an offline TTS synthesis pipeline).
- Do some enterprise Windows machines disable Web Speech online services via Group Policy? (Yes: our SAPI5 offline fallback covers this scenario).

## Links

- [MDN Web Speech API Documentation](https://developer.mozilla.org/en-US/docs/Web/API/Web_Speech_API)
- [W3C Speech API Community Group Specification](https://wicg.github.io/speech-api/)
- [Microsoft Edge Natural Voices Overview](https://learn.microsoft.com/en-us/microsoft-edge/devtools-guide-chromium/speech-synthesis)
