import type { Plan, PlannedStep, RunEvent, Step, User, Workflow } from "@krama/contracts-ts";
import type { TutorialSpec } from "@krama/tutorial-compiler";
import type { TutorialSummary } from "@/types/tutorial";
import giteaTutorialSpecJson from "../../contracts/fixtures/tutorial-spec/gitea-create-repo.json";
import giteaWorkflowJson from "../../contracts/fixtures/gitea-create-repo-workflow.json";
import validWorkflowJson from "../../contracts/fixtures/valid_workflow.json";

export const demoUserFixture: User = {
  id: "e1b2c3d4-0000-4000-8000-000000000001",
  email: "demo@krama.dev",
  display_name: "Demo User",
  created_at: "2026-10-01T00:00:00.000Z",
};

export const giteaWorkflowFixture = giteaWorkflowJson as unknown as Workflow;
export const validWorkflowFixture = validWorkflowJson as unknown as Workflow;
export const giteaTutorialSpecFixture = giteaTutorialSpecJson as unknown as TutorialSpec;

export const tutorialSpecFixtures: Record<string, TutorialSpec> = {
  [giteaTutorialSpecFixture.workflow_id]: giteaTutorialSpecFixture,
  [giteaWorkflowFixture.id]: giteaTutorialSpecFixture,
  "gitea": giteaTutorialSpecFixture,
  "default": giteaTutorialSpecFixture,
  "mock": giteaTutorialSpecFixture,
  "gitea-create-repo": giteaTutorialSpecFixture,
  "github-star-repo": { ...giteaTutorialSpecFixture, title: "Star a repository on GitHub" },
  "github-create-issue-outdated": { ...giteaTutorialSpecFixture, title: "Create an issue with template on GitHub" },
  "gitea-deploy-key-outdated": { ...giteaTutorialSpecFixture, title: "Add deploy key in Gitea repository" },
  "custom-dashboard-export": { ...giteaTutorialSpecFixture, title: "Export analytics report in Custom Portal" },
  "valid-token": giteaTutorialSpecFixture,
  "test-sample-token": giteaTutorialSpecFixture,
};

/** The plan-shaped part of a workflow step (what /plans/{id} returns). */
export function toPlannedStep(s: Step): PlannedStep {
  return {
    seq: s.seq,
    action: s.action,
    target: { role: s.target?.role ?? null, name: s.target?.name ?? null, selector: s.target?.selector ?? null },
    instruction_text: s.instruction_text,
    expected_state: s.expected_state,
    risk: s.risk,
  };
}

export const workflowFixtures: Record<string, Workflow> = {
  [validWorkflowFixture.id]: validWorkflowFixture,
  [giteaWorkflowFixture.id]: giteaWorkflowFixture,
  "gitea": giteaWorkflowFixture,
  "default": giteaWorkflowFixture,
  "mock": giteaWorkflowFixture,
  "gitea-create-repo": giteaWorkflowFixture,
  "github-star-repo": {
    ...giteaWorkflowFixture,
    id: "github-star-repo",
    title: "Star a repository on GitHub",
    target_app: "github",
    created_at: "2026-10-20T10:00:00.000Z",
  },
  "github-create-issue-outdated": {
    ...giteaWorkflowFixture,
    id: "github-create-issue-outdated",
    title: "Create an issue with template on GitHub",
    target_app: "github",
    status: "outdated",
    created_at: "2026-09-15T08:30:00.000Z",
  },
  "gitea-deploy-key-outdated": {
    ...giteaWorkflowFixture,
    id: "gitea-deploy-key-outdated",
    title: "Add deploy key in Gitea repository",
    target_app: "gitea",
    status: "outdated",
    created_at: "2026-08-10T14:15:00.000Z",
  },
  "custom-dashboard-export": {
    ...giteaWorkflowFixture,
    id: "custom-dashboard-export",
    title: "Export analytics report in Custom Portal",
    target_app: "custom",
    created_at: "2026-10-18T16:45:00.000Z",
  },
};

export const mockTutorialSummaries: TutorialSummary[] = [
  {
    id: giteaWorkflowFixture.id,
    title: "Create a repository in local Gitea",
    description: "Initialize and configure a new Git repository with README and license in local Gitea.",
    taskPrompt: "Create a repository in local Gitea",
    target: "gitea",
    status: "verified",
    stepCount: 5,
    durationMs: 90000,
    createdAt: "2026-10-06T12:00:00.000Z",
  },
  {
    id: "github-star-repo",
    title: "Star a repository on GitHub",
    description: "Search for a repository on GitHub and add it to your starred list.",
    taskPrompt: "Star the kubernetes repository on GitHub",
    target: "github",
    status: "verified",
    stepCount: 3,
    durationMs: 45000,
    createdAt: "2026-10-20T10:00:00.000Z",
  },
  {
    id: "github-create-issue-outdated",
    title: "Create an issue with template on GitHub",
    description: "Submit a structured bug report using the repository issue form template.",
    taskPrompt: "Navigate to issues and submit a bug report with markdown template",
    target: "github",
    status: "outdated",
    stepCount: 6,
    durationMs: 120000,
    createdAt: "2026-09-15T08:30:00.000Z",
  },
  {
    id: "gitea-deploy-key-outdated",
    title: "Add deploy key in Gitea repository",
    description: "Configure read-only SSH deploy key in repository settings for automated deployment.",
    taskPrompt: "Configure readonly SSH deploy key in repository settings",
    target: "gitea",
    status: "outdated",
    stepCount: 4,
    durationMs: 60000,
    createdAt: "2026-08-10T14:15:00.000Z",
  },
  {
    id: "custom-dashboard-export",
    title: "Export analytics report in Custom Portal",
    description: "Filter date range and export monthly usage metrics as CSV from custom admin portal.",
    taskPrompt: "Download monthly usage report as CSV from custom portal",
    target: "custom",
    status: "verified",
    stepCount: 5,
    durationMs: 85000,
    createdAt: "2026-10-18T16:45:00.000Z",
  },
];

/**
 * Parses raw SSE wire format string (`event: ...\nid: ...\ndata: ...\n\n`) into typed `RunEvent` objects.
 */
export function parseSseEvents(rawSse: string): RunEvent[] {
  const blocks = rawSse
    .trim()
    .split("\n\n")
    .map((b) => b.trim())
    .filter(Boolean);

  const events: RunEvent[] = [];
  for (const block of blocks) {
    const lines = block.split("\n");
    const dataLine = lines.find((l) => l.startsWith("data: "));
    if (dataLine) {
      const payload = JSON.parse(dataLine.slice("data: ".length));
      events.push(payload as RunEvent);
    }
  }
  return events;
}

export const GITEA_CREATE_REPO_SSE = `event: run.started
id: 1
data: {"type":"run.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":1,"ts":"2026-10-06T12:00:00.000Z","plan_id":"6f1c2a4e-3333-4b8a-9a1b-123456789abc","total_steps":5}

event: step.started
id: 2
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":2,"ts":"2026-10-06T12:00:00.500Z","step_seq":1,"instruction_text":"Open the + menu at the top right."}

event: step.action_done
id: 3
data: {"type":"step.action_done","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":3,"ts":"2026-10-06T12:00:00.829Z","step_seq":1,"screenshot_url":"/screenshots/step-1.png","bbox":[1146,6,56,36]}

event: step.verified
id: 4
data: {"type":"step.verified","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":4,"ts":"2026-10-06T12:00:01.047Z","step_seq":1,"method":["aria"],"confidence":1.0}

event: step.started
id: 5
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":5,"ts":"2026-10-06T12:00:01.110Z","step_seq":2,"instruction_text":"Click New Repository in the menu."}

event: step.action_done
id: 6
data: {"type":"step.action_done","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":6,"ts":"2026-10-06T12:00:01.218Z","step_seq":2,"screenshot_url":"/screenshots/step-2.png","bbox":[1044,44,156,38]}

event: step.verified
id: 7
data: {"type":"step.verified","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":7,"ts":"2026-10-06T12:00:01.450Z","step_seq":2,"method":["url","dom","aria"],"confidence":1.0}

event: step.started
id: 8
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":8,"ts":"2026-10-06T12:00:01.512Z","step_seq":3,"instruction_text":"Enter demo-repo as the repository name."}

event: step.action_done
id: 9
data: {"type":"step.action_done","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":9,"ts":"2026-10-06T12:00:01.825Z","step_seq":3,"screenshot_url":"/screenshots/step-3.png","bbox":[519,262,386,38]}

event: step.verified
id: 10
data: {"type":"step.verified","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":10,"ts":"2026-10-06T12:00:02.100Z","step_seq":3,"method":["dom"],"confidence":1.0}

event: step.started
id: 11
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":11,"ts":"2026-10-06T12:00:02.187Z","step_seq":4,"instruction_text":"Check Initialize Repository to add .gitignore, License and README."}

event: step.action_done
id: 12
data: {"type":"step.action_done","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":12,"ts":"2026-10-06T12:00:02.516Z","step_seq":4,"screenshot_url":"/screenshots/step-4.png","bbox":[519,936,15,15]}

event: step.verified
id: 13
data: {"type":"step.verified","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":13,"ts":"2026-10-06T12:00:02.800Z","step_seq":4,"method":["dom"],"confidence":1.0}

event: step.started
id: 14
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":14,"ts":"2026-10-06T12:00:02.877Z","step_seq":5,"instruction_text":"Click Create Repository button to submit the form."}

event: step.action_done
id: 15
data: {"type":"step.action_done","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":15,"ts":"2026-10-06T12:00:03.410Z","step_seq":5,"screenshot_url":"/screenshots/step-5.png","bbox":[519,650,154,38]}

event: step.verified
id: 16
data: {"type":"step.verified","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":16,"ts":"2026-10-06T12:00:04.100Z","step_seq":5,"method":["url","dom","aria"],"confidence":1.0}

event: run.completed
id: 17
data: {"type":"run.completed","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":17,"ts":"2026-10-06T12:00:04.610Z","workflow_id":"6f1c2a4e-1111-4b8a-9a1b-123456789abc","verified_steps":5,"failed_actions":0}`;

export const giteaEventsFixture: RunEvent[] = parseSseEvents(GITEA_CREATE_REPO_SSE);

export const GITEA_PAUSED_RUN_SSE = `event: run.started
id: 1
data: {"type":"run.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":1,"ts":"2026-10-06T12:00:00.000Z","plan_id":"6f1c2a4e-3333-4b8a-9a1b-123456789abc","total_steps":5}

event: step.started
id: 2
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":2,"ts":"2026-10-06T12:00:00.500Z","step_seq":1,"instruction_text":"Open the + menu at the top right."}

event: step.action_done
id: 3
data: {"type":"step.action_done","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":3,"ts":"2026-10-06T12:00:00.829Z","step_seq":1,"screenshot_url":"/screenshots/step-1.png","bbox":[1146,6,56,36]}

event: step.verified
id: 4
data: {"type":"step.verified","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":4,"ts":"2026-10-06T12:00:01.047Z","step_seq":1,"method":["aria"],"confidence":1.0}

event: step.started
id: 5
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":5,"ts":"2026-10-06T12:00:01.110Z","step_seq":2,"instruction_text":"Click New Repository in the menu."}

event: run.paused
id: 6
data: {"type":"run.paused","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":6,"ts":"2026-10-06T12:00:01.300Z","reason":"destructive_action","step_seq":2,"message":"Destructive action requires confirmation before proceeding"}
`;

export const giteaPausedEventsFixture: RunEvent[] = parseSseEvents(GITEA_PAUSED_RUN_SSE);

export const GITEA_FAILED_RUN_SSE = `event: run.started
id: 1
data: {"type":"run.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":1,"ts":"2026-10-06T12:00:00.000Z","plan_id":"6f1c2a4e-3333-4b8a-9a1b-123456789abc","total_steps":5}

event: step.started
id: 2
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":2,"ts":"2026-10-06T12:00:00.500Z","step_seq":1,"instruction_text":"Open the + menu at the top right."}

event: step.action_done
id: 3
data: {"type":"step.action_done","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":3,"ts":"2026-10-06T12:00:00.829Z","step_seq":1,"screenshot_url":"/screenshots/step-1.png","bbox":[1146,6,56,36]}

event: step.verified
id: 4
data: {"type":"step.verified","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":4,"ts":"2026-10-06T12:00:01.047Z","step_seq":1,"method":["aria"],"confidence":1.0}

event: step.started
id: 5
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":5,"ts":"2026-10-06T12:00:01.110Z","step_seq":2,"instruction_text":"Click New Repository in the menu."}

event: step.failed
id: 6
data: {"type":"step.failed","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":6,"ts":"2026-10-06T12:00:01.400Z","step_seq":2,"expected":{"url_matches":"^/repo/create$","visible":[{"role":"button","name":"Create Repository"}]},"observed":{"url":"/repo/error","title":"500 Internal Server Error"},"screenshot_url":"/mock-observed.png"}

event: run.failed
id: 7
data: {"type":"run.failed","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":7,"ts":"2026-10-06T12:00:01.500Z","error":{"code":"validation_error","message":"Step 2 failed verification: target URL did not match expected path","details":{}}}
`;

export const giteaFailedEventsFixture: RunEvent[] = parseSseEvents(GITEA_FAILED_RUN_SSE);

export const GITEA_REPLAN_RUN_SSE = `event: run.started
id: 1
data: {"type":"run.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":1,"ts":"2026-10-06T12:00:00.000Z","plan_id":"6f1c2a4e-3333-4b8a-9a1b-123456789abc","total_steps":5}

event: step.started
id: 2
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":2,"ts":"2026-10-06T12:00:00.500Z","step_seq":1,"instruction_text":"Open the + menu at the top right."}

event: step.action_done
id: 3
data: {"type":"step.action_done","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":3,"ts":"2026-10-06T12:00:00.829Z","step_seq":1,"screenshot_url":"/mock-observed.png","bbox":[1146,6,56,36]}

event: step.verified
id: 4
data: {"type":"step.verified","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":4,"ts":"2026-10-06T12:00:01.047Z","step_seq":1,"method":["aria"],"confidence":1.0}

event: step.started
id: 5
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":5,"ts":"2026-10-06T12:00:01.110Z","step_seq":2,"instruction_text":"Click New Repository in the menu."}

event: step.failed
id: 6
data: {"type":"step.failed","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":6,"ts":"2026-10-06T12:00:01.400Z","step_seq":2,"expected":{"url_matches":"^/repo/create$","visible":[{"role":"button","name":"Create Repository"}]},"observed":{"url":"/repo/error","title":"500 Internal Server Error"},"screenshot_url":"/mock-observed.png"}

event: run.replanning
id: 7
data: {"type":"run.replanning","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":7,"ts":"2026-10-06T12:00:01.600Z","reason":"Element not found in DOM, attempting alternative locator strategy","attempt":1}

event: run.replanning
id: 8
data: {"type":"run.replanning","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":8,"ts":"2026-10-06T12:00:02.000Z","reason":"Target branch mismatch, replanning remaining execution steps","attempt":2}

event: run.paused
id: 9
data: {"type":"run.paused","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":9,"ts":"2026-10-06T12:00:02.500Z","reason":"recovery_exhausted","step_seq":2,"message":"Automatic recovery budget exhausted after 3 attempts"}
`;

export const giteaReplanEventsFixture: RunEvent[] = parseSseEvents(GITEA_REPLAN_RUN_SSE);

export const GITEA_REPLAN_REVIEW_RUN_SSE = `event: run.started
id: 1
data: {"type":"run.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":1,"ts":"2026-10-06T12:00:00.000Z","plan_id":"6f1c2a4e-3333-4b8a-9a1b-123456789abc","total_steps":5}

event: step.started
id: 2
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":2,"ts":"2026-10-06T12:00:00.500Z","step_seq":1,"instruction_text":"Open the + menu at the top right."}

event: step.action_done
id: 3
data: {"type":"step.action_done","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":3,"ts":"2026-10-06T12:00:00.829Z","step_seq":1,"screenshot_url":"/screenshots/step-1.png","bbox":[1146,6,56,36]}

event: step.verified
id: 4
data: {"type":"step.verified","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":4,"ts":"2026-10-06T12:00:01.047Z","step_seq":1,"method":["aria"],"confidence":1.0}

event: step.started
id: 5
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":5,"ts":"2026-10-06T12:00:01.110Z","step_seq":2,"instruction_text":"Click New Repository in the menu."}

event: step.action_done
id: 6
data: {"type":"step.action_done","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":6,"ts":"2026-10-06T12:00:01.300Z","step_seq":2,"screenshot_url":"/mock-observed.png","bbox":null}

event: step.failed
id: 7
data: {"type":"step.failed","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":7,"ts":"2026-10-06T12:00:01.400Z","step_seq":2,"expected":{"url_matches":"^/repo/create$"},"observed":{"url":"/explore/repos","title":"Explore - Gitea"},"screenshot_url":"/mock-observed.png"}

event: run.replanning
id: 8
data: {"type":"run.replanning","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":8,"ts":"2026-10-06T12:00:01.600Z","reason":"step 2 failed: the URL did not match ^/repo/create$","attempt":1}

event: run.paused
id: 9
data: {"type":"run.paused","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":9,"ts":"2026-10-06T12:00:02.200Z","reason":"replan_review","step_seq":2,"message":"The agent proposes new remaining steps. Allow runs them, deny cancels.","plan_id":"6f1c2a4e-4444-4b8a-9a1b-123456789abc"}
`;

export const giteaReplanReviewEventsFixture: RunEvent[] = parseSseEvents(GITEA_REPLAN_REVIEW_RUN_SSE);

/** The plan a replan_review pause points at: the steps already done plus new remaining steps from seq 2. */
export const replanProposedPlanFixture: Plan = {
  id: "6f1c2a4e-4444-4b8a-9a1b-123456789abc",
  task_id: "mock-task-id",
  revision: 1,
  status: "proposed",
  risk: "low",
  expected_result: "A new repository page is shown",
  steps: [
    ...giteaWorkflowFixture.steps.slice(0, 1).map(toPlannedStep),
    {
      seq: 2,
      action: { type: "navigate", value: "/repo/create" },
      target: {},
      instruction_text: "Open the New Repository page directly.",
      expected_state: { url_matches: "/repo/create" },
      risk: "low",
    },
    ...giteaWorkflowFixture.steps.slice(2).map(toPlannedStep),
  ] as [PlannedStep, ...PlannedStep[]],
  created_at: "2026-10-06T12:00:02.000Z",
};

export const pausedWorkflowFixture: Workflow = {
  ...giteaWorkflowFixture,
  id: "paused",
  title: "Create repository in local Gitea (Paused)",
  status: "running",
  steps: (giteaWorkflowFixture.steps || []).map((s) =>
    s.seq === 2 ? { ...s, risk: "high" } : s
  ),
};

export const failedWorkflowFixture: Workflow = {
  ...giteaWorkflowFixture,
  id: "failed",
  title: "Create repository in local Gitea (Failed)",
  status: "failed",
};

export const replanWorkflowFixture: Workflow = {
  ...giteaWorkflowFixture,
  id: "replan",
  title: "Create repository in local Gitea (Replan)",
  status: "running",
};

export const replanReviewWorkflowFixture: Workflow = {
  ...giteaWorkflowFixture,
  id: "replan-review",
  title: "Create repository in local Gitea (Replan review)",
  status: "running",
};

export const GITEA_BLOCKED_RUN_SSE = `event: run.started
id: 1
data: {"type":"run.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":1,"ts":"2026-10-06T12:00:00.000Z","plan_id":"6f1c2a4e-3333-4b8a-9a1b-123456789abc","total_steps":5}

event: step.started
id: 2
data: {"type":"step.started","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":2,"ts":"2026-10-06T12:00:00.500Z","step_seq":1,"instruction_text":"Open the + menu at the top right."}

event: run.failed
id: 3
data: {"type":"run.failed","run_id":"6f1c2a4e-2222-4b8a-9a1b-123456789abc","seq":3,"ts":"2026-10-06T12:00:01.000Z","error":{"code":"internal","message":"A CAPTCHA challenge was detected on the target page. Automation stops here; finish this step manually.","details":{"reason":"policy_stop","policy_reason":"captcha","step_seq":1}}}
`;

// Policy STOP (CAPTCHA / bot wall / login wall) is not a pause: the backend ends the run with run.failed and
// error.details.reason = "policy_stop", error.details.policy_reason = "captcha" | "auth_wall".
export const giteaBlockedEventsFixture: RunEvent[] = parseSseEvents(GITEA_BLOCKED_RUN_SSE);

export const blockedWorkflowFixture: Workflow = {
  ...giteaWorkflowFixture,
  id: "blocked",
  title: "Create repository in local Gitea (Blocked by Cloudflare)",
  target_url: "http://localhost:3001/login",
  status: "running",
};

export const restrictedWorkflowFixture: Workflow = {
  ...blockedWorkflowFixture,
  id: "restricted",
};

workflowFixtures["paused"] = pausedWorkflowFixture;
workflowFixtures["failed"] = failedWorkflowFixture;
workflowFixtures["replan"] = replanWorkflowFixture;
workflowFixtures["blocked"] = blockedWorkflowFixture;
workflowFixtures["restricted"] = restrictedWorkflowFixture;
workflowFixtures["replan-review"] = replanReviewWorkflowFixture;

import type { RunDetails, RunListItem, StepEvidenceDetail } from "./types";

export const mockRunsList: RunListItem[] = [
  {
    id: "run-1",
    prompt: "Create a repository named demo-repo in local Gitea initialized with README, .gitignore, and license",
    status: "verified",
    createdAt: "2026-10-06T12:00:00Z",
    startedAt: "2026-10-06T12:00:00Z",
    finishedAt: "2026-10-06T12:00:05Z",
    durationSeconds: 5,
    workflowId: giteaWorkflowFixture.id,
    planId: "6f1c2a4e-3333-4b8a-9a1b-123456789abc",
    retryCount: 0,
  },
  {
    id: "run-2",
    prompt: "Create a repository with invalid credentials in Gitea",
    status: "failed",
    createdAt: "2026-10-06T12:15:00Z",
    startedAt: "2026-10-06T12:15:00Z",
    finishedAt: "2026-10-06T12:15:02Z",
    durationSeconds: 2,
    workflowId: "failed",
    planId: "plan-failed-2",
    retryCount: 1,
  },
  {
    id: "run-3",
    prompt: "Delete repository demo-repo permanently",
    status: "paused",
    createdAt: "2026-10-06T12:30:00Z",
    startedAt: "2026-10-06T12:30:00Z",
    finishedAt: null,
    durationSeconds: null,
    workflowId: "paused",
    planId: "plan-paused-3",
    retryCount: 0,
  },
  {
    id: "run-4",
    prompt: "Transfer repository ownership to organization",
    status: "cancelled",
    createdAt: "2026-10-06T12:45:00Z",
    startedAt: "2026-10-06T12:45:00Z",
    finishedAt: "2026-10-06T12:45:03Z",
    durationSeconds: 3,
    workflowId: null,
    planId: "plan-cancelled-4",
    retryCount: 0,
  },
  {
    id: "run-5",
    prompt: "Fork repository kubernetes/kubernetes to personal namespace",
    status: "verified",
    createdAt: "2026-10-06T13:00:00Z",
    startedAt: "2026-10-06T13:00:00Z",
    finishedAt: "2026-10-06T13:00:04Z",
    durationSeconds: 4,
    workflowId: "workflow-fork-5",
    planId: "plan-fork-5",
    retryCount: 0,
  },
  {
    id: "run-6",
    prompt: "Create an issue titled 'Bug: login session timeout' in test-repo",
    status: "verified",
    createdAt: "2026-10-06T13:15:00Z",
    startedAt: "2026-10-06T13:15:00Z",
    finishedAt: "2026-10-06T13:15:03Z",
    durationSeconds: 3,
    workflowId: "workflow-issue-6",
    planId: "plan-issue-6",
    retryCount: 0,
  },
  {
    id: "run-7",
    prompt: "Star repository gitea/gitea and watch releases",
    status: "verified",
    createdAt: "2026-10-06T13:30:00Z",
    startedAt: "2026-10-06T13:30:00Z",
    finishedAt: "2026-10-06T13:30:02Z",
    durationSeconds: 2,
    workflowId: "workflow-star-7",
    planId: "plan-star-7",
    retryCount: 0,
  },
  {
    id: "run-8",
    prompt: "Generate personal access token with repo scope",
    status: "verified",
    createdAt: "2026-10-06T13:45:00Z",
    startedAt: "2026-10-06T13:45:00Z",
    finishedAt: "2026-10-06T13:45:04Z",
    durationSeconds: 4,
    workflowId: "workflow-token-8",
    planId: "plan-token-8",
    retryCount: 0,
  },
  {
    id: "run-9",
    prompt: "Add collaborator alice with write permissions",
    status: "verified",
    createdAt: "2026-10-06T14:00:00Z",
    startedAt: "2026-10-06T14:00:00Z",
    finishedAt: "2026-10-06T14:00:03Z",
    durationSeconds: 3,
    workflowId: "workflow-collab-9",
    planId: "plan-collab-9",
    retryCount: 0,
  },
  {
    id: "run-10",
    prompt: "Create branch feature/auth-redesign from main",
    status: "verified",
    createdAt: "2026-10-06T14:15:00Z",
    startedAt: "2026-10-06T14:15:00Z",
    finishedAt: "2026-10-06T14:15:03Z",
    durationSeconds: 3,
    workflowId: "workflow-branch-10",
    planId: "plan-branch-10",
    retryCount: 0,
  },
  {
    id: "run-11",
    prompt: "Setup webhook for push events to https://ci.example.com",
    status: "failed",
    createdAt: "2026-10-06T14:30:00Z",
    startedAt: "2026-10-06T14:30:00Z",
    finishedAt: "2026-10-06T14:30:02Z",
    durationSeconds: 2,
    workflowId: "workflow-webhook-11",
    planId: "plan-webhook-11",
    retryCount: 2,
  },
  {
    id: "run-12",
    prompt: "Archive repository legacy-backend",
    status: "cancelled",
    createdAt: "2026-10-06T14:45:00Z",
    startedAt: "2026-10-06T14:45:00Z",
    finishedAt: "2026-10-06T14:45:02Z",
    durationSeconds: 2,
    workflowId: "workflow-archive-12",
    planId: "plan-archive-12",
    retryCount: 0,
  },
];

const giteaStepsEvidence: StepEvidenceDetail[] = [
  {
    id: "step-1",
    seq: 1,
    instructionText: "Open the + menu at the top right.",
    actionType: "click",
    targetRole: "menu",
    targetName: "Create…",
    risk: "low",
    status: "verified",
    evidence: {
      method: "aria",
      confidence: 1.0,
      screenshotUrl: "/screenshots/step-1.png",
      observedAt: "2026-10-06T12:00:01.047Z",
      details: { roleMatched: "menu", nameMatched: "Create…" },
    },
    screenshotUrl: "/screenshots/step-1.png",
    expectedState: {
      url_matches: "^/$",
      visible: [{ role: "menuitem", name: "New Repository" }],
    },
    observedState: {
      url: "/",
      title: "demo - Dashboard - Gitea: Git with a cup of tea",
      screenshot_path: "/screenshots/step-1.png",
    },
    timing: { startMs: 2718, endMs: 3047, durationMs: 329 },
  },
  {
    id: "step-2",
    seq: 2,
    instructionText: "Click New Repository in the menu.",
    actionType: "click",
    targetRole: "menuitem",
    targetName: "New Repository",
    risk: "low",
    status: "verified",
    evidence: {
      method: "url_dom",
      confidence: 0.98,
      screenshotUrl: "/screenshots/step-2.png",
      observedAt: "2026-10-06T12:00:01.450Z",
      details: { urlMatched: "/repo/create", domNodesFound: 1 },
    },
    screenshotUrl: "/screenshots/step-2.png",
    expectedState: {
      url_matches: "^/repo/create$",
      visible: [{ role: "heading", name: "New Repository" }],
    },
    observedState: {
      url: "/repo/create",
      title: "New Repository - Gitea: Git with a cup of tea",
      screenshot_path: "/screenshots/step-2.png",
    },
    timing: { startMs: 3110, endMs: 3450, durationMs: 340 },
  },
  {
    id: "step-3",
    seq: 3,
    instructionText: "Enter demo-repo as the repository name.",
    actionType: "fill",
    targetRole: "textbox",
    targetName: "Repository Name *",
    risk: "low",
    status: "verified",
    evidence: {
      method: "url_dom",
      confidence: 1.0,
      screenshotUrl: "/screenshots/step-3.png",
      observedAt: "2026-10-06T12:00:02.100Z",
      details: { inputValidated: "demo-repo" },
    },
    screenshotUrl: "/screenshots/step-3.png",
    expectedState: {
      field_values: [{ role: "textbox", name: "Repository Name *", value: "demo-repo" }],
    },
    observedState: {
      url: "/repo/create",
      title: "New Repository - Gitea: Git with a cup of tea",
      screenshot_path: "/screenshots/step-3.png",
    },
    timing: { startMs: 3512, endMs: 4100, durationMs: 588 },
  },
  {
    id: "step-4",
    seq: 4,
    instructionText: "Check Initialize Repository to add .gitignore, License and README.",
    actionType: "click",
    targetRole: "checkbox",
    targetName: "Initialize Repository",
    risk: "low",
    status: "verified",
    evidence: {
      method: "network",
      confidence: 0.85,
      screenshotUrl: "/screenshots/step-4.png",
      observedAt: "2026-10-06T12:00:02.800Z",
      details: { networkStatus: 200, responseValid: true },
    },
    screenshotUrl: "/screenshots/step-4.png",
    expectedState: {
      checked: [{ role: "checkbox", name: "Initialize Repository" }],
    },
    observedState: {
      url: "/repo/create",
      title: "New Repository - Gitea: Git with a cup of tea",
      screenshot_path: "/screenshots/step-4.png",
    },
    timing: { startMs: 4187, endMs: 4800, durationMs: 613 },
  },
  {
    id: "step-5",
    seq: 5,
    instructionText: "Click Create Repository button to submit the form.",
    actionType: "click",
    targetRole: "button",
    targetName: "Create Repository",
    risk: "low",
    status: "verified",
    evidence: {
      method: "vision",
      confidence: 0.95,
      screenshotUrl: "/screenshots/step-5.png",
      observedAt: "2026-10-06T12:00:04.100Z",
      details: { visualTargetMatched: true, perceptualSimilarity: 0.96 },
    },
    screenshotUrl: "/screenshots/step-5.png",
    expectedState: {
      url_matches: "^/demo/demo-repo$",
    },
    observedState: {
      url: "/demo/demo-repo",
      title: "demo/demo-repo - Gitea: Git with a cup of tea",
      screenshot_path: "/screenshots/step-5.png",
    },
    timing: { startMs: 4877, endMs: 5410, durationMs: 533 },
  },
];

export const mockRunDetails: Record<string, RunDetails> = {
  "run-1": {
    run: mockRunsList[0],
    workflow: giteaWorkflowFixture,
    targetUrl: "http://localhost:3001",
    targetApp: "gitea",
    steps: giteaStepsEvidence,
    summary: {
      totalSteps: 5,
      verifiedSteps: 5,
      failedSteps: 0,
      durationSeconds: 5,
    },
  },
  [giteaWorkflowFixture.run_id ?? "6f1c2a4e-2222-4b8a-9a1b-123456789abc"]: {
    run: mockRunsList[0],
    workflow: giteaWorkflowFixture,
    targetUrl: "http://localhost:3001",
    targetApp: "gitea",
    steps: giteaStepsEvidence,
    summary: {
      totalSteps: 5,
      verifiedSteps: 5,
      failedSteps: 0,
      durationSeconds: 5,
    },
  },
  "default": {
    run: mockRunsList[0],
    workflow: giteaWorkflowFixture,
    targetUrl: "http://localhost:3001",
    targetApp: "gitea",
    steps: giteaStepsEvidence,
    summary: {
      totalSteps: 5,
      verifiedSteps: 5,
      failedSteps: 0,
      durationSeconds: 5,
    },
  },
  "run-2": {
    run: mockRunsList[1],
    workflow: failedWorkflowFixture,
    targetUrl: "http://localhost:3001",
    targetApp: "gitea",
    steps: [
      giteaStepsEvidence[0],
      {
        id: "step-failed-2",
        seq: 2,
        instructionText: "Click New Repository in the menu.",
        actionType: "click",
        targetRole: "menuitem",
        targetName: "New Repository",
        risk: "low",
        status: "failed",
        evidence: {
          method: "url_dom",
          confidence: 0.45,
          screenshotUrl: "/mock-observed.png",
          observedAt: "2026-10-06T12:15:01.400Z",
          details: { error: "500 Internal Server Error: target URL /repo/create did not match /repo/error" },
        },
        screenshotUrl: "/mock-observed.png",
        expectedState: { url_matches: "^/repo/create$" },
        observedState: { url: "/repo/error", title: "500 Internal Server Error" },
        timing: { startMs: 1110, endMs: 1400, durationMs: 290 },
      },
    ],
    summary: {
      totalSteps: 5,
      verifiedSteps: 1,
      failedSteps: 1,
      durationSeconds: 2,
    },
  },
  "run-3": {
    run: mockRunsList[2],
    workflow: pausedWorkflowFixture,
    targetUrl: "http://localhost:3001",
    targetApp: "gitea",
    steps: [
      {
        ...giteaStepsEvidence[0],
        screenshotUrl: undefined,
        evidence: {
          ...giteaStepsEvidence[0].evidence,
          screenshotUrl: undefined,
        },
      },
      {
        ...giteaStepsEvidence[1],
        screenshotUrl: "/screenshots/non-existent-broken.png",
        evidence: {
          ...giteaStepsEvidence[1].evidence,
          screenshotUrl: "/screenshots/non-existent-broken.png",
        },
      },
    ],
    summary: {
      totalSteps: 2,
      verifiedSteps: 2,
      failedSteps: 0,
      durationSeconds: null,
    },
  },
};
