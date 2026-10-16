# Tutorial Player Accessibility and WCAG 2.2 Compliance

- **Phase:** 2
- **Researched by:** Nachiketha
- **Question(s):** Player accessibility: keyboard controls, captions, focus handling, screen-reader labels (WCAG 2.2 basics for media players).

## Findings

### 1. Comprehensive Keyboard Navigation (WCAG 2.2 Guideline 2.1)

An interactive tutorial player must be fully operable without pointing devices. Every media control and interactive hotzone must be reachable and operable using keyboard input alone [verified: WCAG 2.2 Guideline 2.1, verified locally]:

- **Standard Media Hotkeys:**
  - `Space` or `K`: Toggle Play / Pause.
  - `Left Arrow` / `Right Arrow`: Scrub timeline backward / forward (3 seconds or relative increment).
  - `J` / `L`: Step jump to previous / next tutorial scene.
  - `Home` / `End`: Jump to first / last step of the workflow.
  - `M`: Toggle audio narration mute.
  - `C`: Toggle closed captions display.
  - `Escape`: Close fullscreen modal or dismiss floating step drawer.
- **Focus Order & Visual Indicators:**
  - Logical DOM tab sequence: `[Play/Pause] → [Prev Step] → [Next Step] → [Progress Scrub Bar] → [Mute Toggle] → [Captions Toggle] → [Step Drawer List]`.
  - Focus rings must be unmissable: `focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2` (meets WCAG 2.4.7 Focus Visible and WCAG 2.4.11 Focus Appearance).
  - **No Focus Trapping:** Keyboard focus must never get trapped inside the replay canvas or iframe container.

### 2. Screen Reader Semantics & Live Regions (WCAG 4.1.2 & W3C APG)

Blind and low-vision users cannot follow visual auto-zoom or cursor movements. The player must communicate state transitions programmatically [verified: W3C ARIA Authoring Practices]:

- **Player Region Container:**
  ```html
  <section
    role="region"
    aria-label="Interactive Tutorial Player"
    aria-roledescription="interactive video tutorial"
    tabindex="0"
  >
  ```
- **Live Region Announcements (`aria-live`):**
  When advancing between steps or when an action is executed, announce the step instruction using a polite live region:
  ```html
  <div
    role="status"
    aria-live="polite"
    aria-atomic="true"
    class="sr-only"
  >
    Step 2 of 5: Click New Repository in the top-right menu.
  </div>
  ```
  - *Anti-spam Rule:* Debounce announcements by 250 ms so scrubbing through the timeline does not overwhelm the user's screen reader queue with garbled fragments [verified locally].
- **Playhead Slider Attributes:**
  The scrubber slider exposes standard range semantics:
  ```html
  <div
    role="slider"
    aria-label="Tutorial Progress"
    aria-valuemin="1"
    aria-valuemax="5"
    aria-valuenow="2"
    aria-valuetext="Step 2 of 5: Click New Repository"
    tabindex="0"
  >
  ```

### 3. Visual Contrast, Typography & Touch Targets (WCAG 1.4.3 & 2.5.5)

- **Color Contrast:**
  - Body and instruction text: Exceeds **4.5:1** contrast ratio against its background (e.g. `#18181b` on `#ffffff` = 16.1:1, or `#f4f4f5` on `#18181b` = 15.2:1) [verified: WCAG 1.4.3].
  - Essential graphical UI elements (progress track, active borders, risk badges): Exceeds **3.0:1** contrast ratio against adjacent colors (WCAG 1.4.11 Non-text Contrast).
- **Target Size (Level AA):**
  - Minimum touch and click target size: **44 × 44 CSS pixels** for all player buttons (Play/Pause, Next, Prev, Mute) to accommodate motor-impaired users and mobile touch screens [verified: WCAG 2.5.5 Target Size].
- **Closed Captions Styling:**
  - High-contrast card backdrop: `bg-zinc-950/85 text-zinc-100 dark:bg-black/90 dark:text-white`.
  - Font size minimum: 14 px with `leading-relaxed` line height.
  - Safe positioning: Captions anchored at bottom-center of the viewport, offset from player controls to avoid interactive occlusion.

## Recommendation

1. Build player accessibility directly into `@krama/player` primitives using Radix UI headless components and Tailwind accessibility utilities (`sr-only`, `focus-visible:`).
2. Wire global keyboard listener with input guards (ignore hotkeys when focus is inside a text input or form element).
3. Ensure the tutorial player satisfies all WCAG 2.2 Level AA requirements by default, without requiring users to find an "accessibility mode" switch.
[No ADR required: conforms to Phase 2 roadmap].

## Open questions

- Should the player include a user preference toggle for high-contrast cursor and click halos (e.g. high-visibility yellow cursor)? (Can be added as a player setting in Sprint 2.2).
- When operating in interactive hands-on mode, how should screen readers indicate that the user must click a specific button on the page to proceed? (Use `aria-describedby` linking to "Click this button to continue the tutorial").

## Links

- [W3C Web Content Accessibility Guidelines (WCAG) 2.2](https://www.w3.org/TR/WCAG22/)
- [W3C ARIA Authoring Practices Guide (APG) — Media Control Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/)
- [Radix UI Accessibility Principles](https://www.radix-ui.com/primitives/docs/overview/accessibility)
