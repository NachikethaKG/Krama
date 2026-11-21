import { CheckCheck, GraduationCap, ListChecks, MessageCircleQuestion, Play, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

/**
 * The six stages of Krama's pipeline. Each has its own colour, used everywhere that stage appears. Their words
 * (label, verb, blurb) are UI text: common.ui.stages.<key> in the messages (#424).
 */
export type StageKey = "ask" | "plan" | "approve" | "run" | "verify" | "learn";

export interface Stage {
  key: StageKey;
  color: string;
  tone: string; // CSS class that sets --kr-tone
  icon: LucideIcon;
}

export const STAGES: Stage[] = [
  {
    key: "ask",
    color: "var(--ask)",
    tone: "kr-ask",
    icon: MessageCircleQuestion,
  },
  {
    key: "plan",
    color: "var(--plan)",
    tone: "kr-plan",
    icon: ListChecks,
  },
  {
    key: "approve",
    color: "var(--approve)",
    tone: "kr-approve",
    icon: ShieldCheck,
  },
  {
    key: "run",
    color: "var(--run)",
    tone: "kr-run",
    icon: Play,
  },
  {
    key: "verify",
    color: "var(--verify)",
    tone: "kr-verify",
    icon: CheckCheck,
  },
  {
    key: "learn",
    color: "var(--learn)",
    tone: "kr-learn",
    icon: GraduationCap,
  },
];

export const STAGE: Record<StageKey, Stage> = Object.fromEntries(STAGES.map((s) => [s.key, s])) as Record<
  StageKey,
  Stage
>;
