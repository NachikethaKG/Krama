# Phase 3 UI Improvement Tracking

This ledger documents the triage and routing of all UX and UI rough edges collected from the Phase 2 demo and exit gate ([#83](https://github.com/NachikethaKG/Krama/issues/83)). Each item is assigned to its owning Phase 3 screen issue or resolved directly.

---

## 1. UI Improvement Tracking Matrix

| Surface / Item | Phase 2 Problem | Owning Issue | Resolution / Status |
| :--- | :--- | :--- | :--- |
| **Landing Page** | Dev-only `"API ok (version 0.1.0)"` health string centered on page | [#275](https://github.com/NachikethaKG/Krama/issues/275) / This PR | **Resolved:** Replaced with product landing hero, quick navigation CTAs, and discreet footer status indicator. |
| **Run / Execution** | Plain run view: no clear step checklist, status transitions, or live screenshot feed | [#99](https://github.com/NachikethaKG/Krama/issues/99) | **In Progress:** Implementing SSE live event stream checklist, live screenshot cards, and replan review modals. |
| **Dashboard / Auth** | No unified logged-in dashboard view, missing sign-in state and workflow statistics | [#97](https://github.com/NachikethaKG/Krama/issues/97) | **Planned:** Building App Router `/dashboard` layout, CSRF protection (`X-Krama: 1`), and seeded auth (`demo@krama.dev`). |
| **Tutorial Library** | Inability to browse, search, or filter past workflows across targets | [#93](https://github.com/NachikethaKG/Krama/issues/93) | **Planned:** Target picker (Gitea vs GitHub), keyword search, status filters, and tutorial catalog cards. |
| **Share View** | Raw player controls exposed without a shareable, read-only boundary | [#98](https://github.com/NachikethaKG/Krama/issues/98) | **Planned:** Dedicated `/share/[token]` route with unguessable tokens, manual revoke, and viewer-only controls. |
| **Usability Baseline** | Need structured external validation of resolved Phase 3 screens | [#103](https://github.com/NachikethaKG/Krama/issues/103) | **Planned:** 5-person think-aloud usability testing evaluating all resolved screens on live benchmark tasks. |

---

## 2. Screen-by-Screen Breakdown & Acceptance Mapping

### 1. Landing Page (`/`) — Closed in [#275](https://github.com/NachikethaKG/Krama/issues/275)
- **Problem:** Developer health check (`frontend/components/api-status.tsx`) was rendered as prominent center text.
- **Resolution:**
  - Removed raw dev health text from viewports.
  - Implemented product landing hero:
    - Headline: *"Interactive Tutorials Recorded From Real UI Actions"*
    - Clear value proposition: *"Krama plans, executes, and verifies workflows headlessly on real sites, compiling them into interactive step-by-step guides."*
    - Primary CTA: **Go to Dashboard** (`/dashboard`).
    - Secondary CTA: **Explore Tutorials** (`/tutorials`).
    - Quick Action: **+ Create Workflow** (`/runs/new`).
  - Moved API status into a discreet badge in the footer (`ApiStatusBadge` with operational dot indicator).
  - Added non-intrusive offline notification banner when backend services are disconnected.

### 2. Live Agent Execution Screen (`/runs/[id]/live`) — Issue [#99](https://github.com/NachikethaKG/Krama/issues/99)
- **Problem:** Phase 2 run view was static, lacking step progression visibility, real-time feedback, and live action screenshots.
- **Requirements:**
  - Server-Sent Events (SSE) stream subscribing to `GET /api/v1/runs/{id}/events`.
  - Live step checklist with dynamic state indicators (`pending`, `executing`, `verified`, `failed`).
  - Live screenshot card updating on each step execution.
  - Replan approval modal with human takeover options (Allow / Deny).

### 3. Authenticated Dashboard (`/dashboard`) — Issue [#97](https://github.com/NachikethaKG/Krama/issues/97)
- **Problem:** No central home for users after starting the app; authentication status was implicit.
- **Requirements:**
  - App Router layout for authenticated users (`/dashboard`).
  - Seeded participant login (`demo@krama.dev`) with FastAPI HTTP-only cookie forwarding.
  - Overview cards: total workflows created, verified tutorials, active runs.
  - Recent runs table with status badges and quick links.

### 4. Tutorial Library & Filtering (`/tutorials`) — Issue [#93](https://github.com/NachikethaKG/Krama/issues/93)
- **Problem:** Users could only view tutorials by knowing their direct IDs or through runs.
- **Requirements:**
  - Grid view of compiled tutorials (`TutorialSpec`).
  - Filter by target application (Gitea vs GitHub).
  - Search by task title or description.
  - Card previews displaying duration, step count, and verification confidence.

### 5. Shareable Read-Only Player (`/share/[token]`) — Issue [#98](https://github.com/NachikethaKG/Krama/issues/98)
- **Problem:** Replay viewer exposed author-level controls with no read-only public sharing link.
- **Requirements:**
  - Public route `/share/[token]` backed by `secrets.token_urlsafe(32)`.
  - Read-only player with step progress bar, camera auto-zoom, and synchronized captions/speech.
  - Revoke token button in author dashboard.

### 6. Usability Testing & Verification — Issue [#103](https://github.com/NachikethaKG/Krama/issues/103)
- **Goal:** Verify that the UI improvements eliminate user confusion on all Phase 3 screens.
- **Protocol:**
  - 5 external participants using think-aloud protocol.
  - Evaluation of landing page clarity, workflow creation, live execution monitoring, and tutorial playback.
  - Usability findings logged and converted into post-MVP issues.
