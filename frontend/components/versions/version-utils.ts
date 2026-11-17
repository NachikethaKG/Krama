import type { StepDiff, WorkflowVersion } from "@krama/contracts-ts";
import type { StepDiffItem, WorkflowVersionRecord } from "@/types/tutorial";

function extractFieldValue(val: unknown): string | undefined {
  if (val === undefined || val === null) return undefined;
  if (typeof val === "string") return val;
  if (typeof val === "object") {
    const obj = val as Record<string, unknown>;
    if (typeof obj.selector === "string") return obj.selector;
    if (typeof obj.name === "string") return obj.name;
    if (typeof obj.text === "string") return obj.text;
    if (typeof obj.value === "string") return obj.value;
    return JSON.stringify(val);
  }
  return String(val);
}

export function parseStepDiffs(changeSummary?: StepDiff | null): StepDiffItem[] {
  if (!changeSummary || !Array.isArray(changeSummary.steps)) {
    return [];
  }

  return changeSummary.steps.map((step, idx) => {
    const stepIndex = step.new_seq ?? step.old_seq ?? idx + 1;
    const isUnchanged = step.kind === "same";
    const isWording = step.category === "wording";

    let oldLabel: string | undefined;
    let newLabel: string | undefined;
    let oldSelector: string | undefined;
    let newSelector: string | undefined;
    let oldCaption: string | undefined;
    let newCaption: string | undefined;

    if (Array.isArray(step.fields)) {
      for (const f of step.fields) {
        if (f.field.includes("selector")) {
          oldSelector = extractFieldValue(f.from);
          newSelector = extractFieldValue(f.to);
        } else if (f.field.includes("name") || f.field.includes("label") || f.field.includes("target")) {
          oldLabel = extractFieldValue(f.from);
          newLabel = extractFieldValue(f.to);
        } else if (f.field.includes("instruction_text") || f.field.includes("caption")) {
          oldCaption = extractFieldValue(f.from);
          newCaption = extractFieldValue(f.to);
        }
      }
    }

    let changeType: "locator_healed" | "wording_only" | "unchanged" = "unchanged";
    if (!isUnchanged) {
      if (isWording || (!oldSelector && !newSelector && !oldLabel && !newLabel && (oldCaption || newCaption))) {
        changeType = "wording_only";
      } else {
        changeType = "locator_healed";
      }
    }

    return {
      stepIndex,
      stepTitle: step.summary || (isUnchanged ? `Step ${stepIndex} (Verified)` : `Step ${stepIndex} (${isWording ? "Wording Updated" : "Locator Healed"})`),
      changeType,
      oldLabel,
      newLabel,
      oldSelector,
      newSelector,
      oldCaption,
      newCaption,
    };
  });
}

export function normalizeVersionRecord(
  raw: WorkflowVersion | WorkflowVersionRecord
): WorkflowVersionRecord {
  // If it's already a full WorkflowVersionRecord
  if ("version" in raw && typeof raw.version === "string" && "stepDiffs" in raw && Array.isArray(raw.stepDiffs)) {
    return raw as WorkflowVersionRecord;
  }

  const wv = raw as WorkflowVersion;
  const stepDiffs = parseStepDiffs(wv.change_summary);
  const changedSteps = stepDiffs.filter((s) => s.changeType !== "unchanged");

  const isWordingOnly =
    changedSteps.length > 0 && changedSteps.every((s) => s.changeType === "wording_only");

  let changeSummaryText = "Baseline version. No prior changes.";
  if (wv.change_summary) {
    if (changedSteps.length === 0) {
      changeSummaryText = "Identical verification pass without step alterations.";
    } else {
      const summaryParts = changedSteps.map((s) => {
        if (s.changeType === "locator_healed") {
          return `Step ${s.stepIndex}: locator healed (${s.oldLabel || s.oldSelector || "target"} → ${s.newLabel || s.newSelector || "healed"})`;
        }
        return `Step ${s.stepIndex}: wording updated`;
      });
      changeSummaryText = summaryParts.join("; ");
    }
  }

  // Format version string (e.g. revision 1 -> v1.0, revision 2 -> v1.1)
  const rawObj = raw as unknown as Record<string, unknown>;
  const versionString = typeof rawObj.version === "string"
    ? rawObj.version
    : wv.revision === 1
    ? "v1.0"
    : `v1.${wv.revision - 1}`;

  // Normalized status
  let status: WorkflowVersionRecord["status"] = "archived";
  if (wv.status === "current") {
    status = wv.source === "heal" ? "auto-updated" : "active";
  } else if (wv.status === "pending_review" || (wv.status as string) === "heal_pending") {
    status = "heal_pending";
  } else if (wv.source === "heal") {
    status = "auto-updated";
  } else {
    status = "archived";
  }

  return {
    id: wv.id,
    version: versionString,
    status,
    changeSummary: changeSummaryText,
    isWordingOnly,
    createdAt: wv.created_at,
    stepDiffs,
  };
}
