import { CheckCheck, GraduationCap, ListChecks, MessageCircleQuestion, Play, ShieldCheck } from "lucide-react";
import type { LucideIcon } from "lucide-react";

/** The six stages of Krama's pipeline. Each has its own colour, used everywhere that stage appears. */
export type StageKey = "ask" | "plan" | "approve" | "run" | "verify" | "learn";

export interface Stage {
  key: StageKey;
  label: string;
  verb: string;
  blurb: string;
  color: string;
  tone: string; // CSS class that sets --kr-tone
  icon: LucideIcon;
}

export const STAGES: Stage[] = [
  {
    key: "ask",
    label: "Ask",
    verb: "You ask",
    blurb: "Type what you want to learn, in plain words.",
    color: "var(--ask)",
    tone: "kr-ask",
    icon: MessageCircleQuestion,
  },
  {
    key: "plan",
    label: "Plan",
    verb: "Krama plans",
    blurb: "Gemini reads the real page and writes every step up front.",
    color: "var(--plan)",
    tone: "kr-plan",
    icon: ListChecks,
  },
  {
    key: "approve",
    label: "Approve",
    verb: "You approve",
    blurb: "Nothing runs until you say so. Risky steps ask again.",
    color: "var(--approve)",
    tone: "kr-approve",
    icon: ShieldCheck,
  },
  {
    key: "run",
    label: "Run",
    verb: "The agent runs",
    blurb: "A real browser does the task while you watch live.",
    color: "var(--run)",
    tone: "kr-run",
    icon: Play,
  },
  {
    key: "verify",
    label: "Verify",
    verb: "Every step is checked",
    blurb: "URL, page and network evidence prove each step worked.",
    color: "var(--verify)",
    tone: "kr-verify",
    icon: CheckCheck,
  },
  {
    key: "learn",
    label: "Learn",
    verb: "You learn",
    blurb: "An interactive tutorial replays the real recorded UI.",
    color: "var(--learn)",
    tone: "kr-learn",
    icon: GraduationCap,
  },
];

export const STAGE: Record<StageKey, Stage> = Object.fromEntries(STAGES.map((s) => [s.key, s])) as Record<
  StageKey,
  Stage
>;
