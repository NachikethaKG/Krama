# 5-Person Think-Aloud Usability Testing Protocol

- **Phase:** 3
- **Researched by:** Nachiketha
- **Question(s):** Usability testing: how to run a 5-person think-aloud test: tasks, what to observe, how to record findings.

## Findings

### 1. The 5-User Think-Aloud Testing Methodology

Phase 3 Sprint 3.3 specifies: *"Run the usability test with 3–5 people outside the team; turn findings into issues."* [verified: phase-3-mvp.md].

- **Theoretical Foundation:** Jakob Nielsen's empirical testing model establishes that testing with **5 participants discovers ~85% of all usable UI defects and conceptual misalignments** [verified: Nielsen Norman Group, "Why You Only Need to Test with 5 Users"]. Beyond 5 users, findings rapidly encounter diminishing returns with repeated overlap.
- **Session Format:**
  - **Duration:** 30 minutes per participant [verified: Nielsen Norman Group].
  - **Participant Profile:** 5 software developers or computer science students who are unfamiliar with Krama's internal codebase and architecture.
  - **Method:** Concurrent Think-Aloud (CTA). The participant verbalizes their thought process, expectations, hesitations, and confusion continuously while interacting with the UI.
  - **Facilitator Role:** Neutral proctor. Introduces the context, provides scenario cards, and asks neutral open prompts (*"What are you looking at right now?"*, *"What did you expect to happen when you clicked that?"*). Never defends the design or explains how the software works.

### 2. Representative Evaluation Tasks (3 Core Scenarios)

The test evaluates the three primary user journeys of Krama: tutorial creation/approval, tutorial player consumption, and human-in-the-loop safety confirmation [verified locally]:

#### Task 1: Generate & Approve a Tutorial from Natural Language (10 mins)
- **User Prompt:** *"You want to teach a new teammate how to create a public repository on GitHub with an initialized README. Use Krama to generate this tutorial."*
- **Workflow:**
  1. Navigate to Krama home / task input screen.
  2. Input task prompt: `"Create a public GitHub repository named demo-repo with a README"`.
  3. Inspect proposed multi-step execution plan on the approval screen.
  4. Edit/refine one instruction step description.
  5. Click `"Approve & Execute"` and observe the live execution stream.

#### Task 2: Follow a Tutorial Using Keyboard-Only Player Controls (10 mins)
- **User Prompt:** *"You are a developer following a Krama tutorial for creating a branch. Navigate through the tutorial using only your keyboard without touching the mouse or trackpad."*
- **Workflow:**
  1. Open the compiled tutorial player at `/tutorials/[id]`.
  2. Use standard keyboard hotkeys (`Space`/`K` for play/pause, `Left`/`Right` to scrub 3 seconds, `J`/`L` to skip steps, `M` to mute narration, `C` to toggle captions).
  3. Observe whether camera auto-zoom, click ripple halos, and captions make each UI action immediately obvious.
  4. Follow step checklist and complete the interactive tutorial.

#### Task 3: Encounter and Resolve a High-Risk Safety Confirmation (10 mins)
- **User Prompt:** *"Krama is executing an automated cleanup task that attempts to delete an existing feature branch. Review what the agent is doing and decide whether to let it proceed."*
- **Workflow:**
  1. Agent pauses execution when detecting the GitHub Danger Zone button.
  2. `PolicyConfirmationModal` appears over the live view with risk details (`RiskLevel.HIGH`).
  3. Participant reads the danger explanation and target selector.
  4. Participant chooses to approve or reject the action.

### 3. Key Observation Metrics & Friction Signals

The observer logs structured observations across four quantitative and qualitative metrics [verified locally]:

| Dimension | Target Metric / Benchmark | Friction Signals to Watch For |
|---|---|---|
| **Time-to-Comprehension** | $< 15$ seconds to grasp agent state and next required action. | Squinting, silent pausing ($> 10$ s), re-reading instructional text multiple times, asking *"What is happening now?"* |
| **Control Discoverability** | Participant discovers keyboard shortcuts and scrubber without coaching. | Cursor hunting for buttons, attempting to drag timeline without clicking, missing closed-caption controls. |
| **Safety Modal Clarity** | Participant correctly identifies *why* the run paused and what will happen if approved. | Blindly clicking "Approve" without reading; or confusion over why a branch delete is considered high risk. |
| **Task Completion Rate** | $\ge 80\%$ unassisted task completion across all 5 participants. | Abandoning task, getting permanently stuck, or needing facilitator intervention to proceed. |

### 4. Structured Issue Filing Template

Observations during usability sessions are converted directly into actionable GitHub issues for Sprint 3.3 [verified locally]:

```markdown
### [Usability] <Component>: <Clear description of participant confusion or failure>

- **Participant:** P1 / P2 / P3 / P4 / P5
- **Task:** Task 1 (Plan & Approval) / Task 2 (Player) / Task 3 (Risk Modal)
- **Severity:** Blocker (Task failed) | Major (Severe confusion / delayed > 30s) | Minor (Polish / cosmetic)

#### Observed Behavior
<What the participant did and verbatim quote of what they said while thinking aloud>

#### Expected Behavior
<What the participant expected the interface to do>

#### Root Cause
<Why the interface induced this misunderstanding (e.g., hidden hotkey cheat sheet, ambiguous button copy, low contrast)>

#### Actionable Remediation for Sprint 3.3
<Concrete UI/UX change to implement>
```

## Recommendation

1. **Execute Usability Study in Early Sprint 3.3:**
   - Run 5 individual 30-minute sessions using the local Docker/Gitea/GitHub test environment on Nachiketha's laptop.
2. **Standardize Test Materials:**
   - Store the facilitator script, task scenario cards, and note-taking observation sheets in `benchmarks/usability/`.
3. **Turn Findings Directly into Sprint 3.3 GitHub Issues:**
   - File issues with the `usability` label, triage by severity, and prioritize fixes before final MVP exit verification.

[No ADR required: directly operationalizes Phase 3 Sprint 3.3 usability testing commitments].

## Open questions

- Should sessions be recorded via screen capture (e.g. OBS Studio or browser recording with participant consent)? (Yes: screen capture + audio provides an objective record to review subtle cursor hesitation and exact quotes).
- What compensation or incentive should be provided to student volunteers? (Standard coffee/snack voucher or peer reciprocity).

## Links

- [Nielsen Norman Group — Why You Only Need to Test with 5 Users](https://www.nngroup.com/articles/why-you-only-need-to-test-with-5-users/)
- [Nielsen Norman Group — Thinking Aloud: The #1 Usability Tool](https://www.nngroup.com/articles/thinking-aloud-the-1-usability-tool/)
- [Steve Krug — *Rocket Surgery Made Easy: The Do-It-Yourself Guide to Finding and Fixing Usability Problems*](https://sensible.com/rocket-surgery-made-easy/)
- [Krama Phase 3 MVP Sprint Plan](file:///c:/Git/Krama/docs/phases/phase-3-mvp.md)
