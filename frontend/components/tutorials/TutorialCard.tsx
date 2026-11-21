"use client";

import Link from "next/link";
import { ArrowUpRight, Box, Clock, Globe, Layers } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { TiltCard } from "@/components/ui";
import type { TargetPlatform, TutorialSummary } from "@/types/tutorial";
import { TutorialStatusBadge } from "./TutorialStatusBadge";

export interface TutorialCardProps {
  tutorial: TutorialSummary;
  /** Position in its grid: picks the card's spectrum colour. Without it the colour comes from the id. */
  index?: number;
  onInspectDiff?: (tutorial: TutorialSummary) => void;
}

/** Every card wears a different spectrum colour, so a grid of tutorials reads like the Krama spectrum. */
const TONES = ["kr-learn", "kr-ask", "kr-run", "kr-plan", "kr-verify", "kr-approve"];

function toneFor(tutorial: TutorialSummary, index?: number): string {
  if (index !== undefined) return TONES[index % TONES.length];
  let hash = 0;
  for (const ch of tutorial.id) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return TONES[hash % TONES.length];
}

function formatDuration(durationMs: number, t: ReturnType<typeof useTranslations>): string {
  if (!durationMs || durationMs <= 0) return t("card.underAMinute");
  if (durationMs < 60000) return t("card.underAMinute");
  const minutes = Math.round(durationMs / 60000);
  return t("card.aboutMinutes", { minutes });
}

function formatDate(isoString: string, locale: string): string {
  try {
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString(locale, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return isoString;
  }
}

const BADGE = "inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-bold";

function TargetBadge({ target }: { target: TargetPlatform }) {
  const t = useTranslations("library");
  switch (target) {
    case "github":
      return (
        <span
          data-testid="tutorial-card-target"
          data-target="github"
          className={`${BADGE} border-white/20 bg-white/10 text-white`}
        >
          <svg className="size-3.5 fill-current" viewBox="0 0 24 24" aria-hidden="true">
            <path
              fillRule="evenodd"
              clipRule="evenodd"
              d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.53 1.032 1.53 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0112 6.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0022 12.017C22 6.484 17.522 2 12 2z"
            />
          </svg>
          GitHub
        </span>
      );
    case "custom":
      return (
        <span
          data-testid="tutorial-card-target"
          data-target="custom"
          className={`${BADGE} border-approve/50 bg-approve/15 text-approve`}
        >
          <Globe className="size-3.5" aria-hidden="true" />
          {t("card.targetCustom")}
        </span>
      );
    case "gitea":
    default:
      return (
        <span
          data-testid="tutorial-card-target"
          data-target="gitea"
          className={`${BADGE} border-verify/50 bg-verify/15 text-verify`}
        >
          <Box className="size-3.5" aria-hidden="true" />
          Gitea
        </span>
      );
  }
}

/**
 * A search snippet: plain text with `<mark>` around matched words (#135). Only the marks become elements; all
 * other text, including anything that looks like HTML, is shown as text.
 */
export function MarkedText({ text }: { text: string }) {
  const parts = text.split(/(<mark>[\s\S]*?<\/mark>)/g);
  return (
    <>
      {parts.map((part, i) =>
        part.startsWith("<mark>") && part.endsWith("</mark>") ? (
          <mark key={i} className="rounded bg-learn/25 px-0.5 text-white">
            {part.slice(6, -7)}
          </mark>
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}

export function TutorialCard({ tutorial, index, onInspectDiff }: TutorialCardProps) {
  const t = useTranslations("library");
  const locale = useLocale();
  const durationLabel = formatDuration(tutorial.durationMs, t);
  const dateLabel = formatDate(tutorial.createdAt, locale);
  const tone = toneFor(tutorial, index);

  return (
    <TiltCard max={6} className={`${tone} kr-tone-card group h-full rounded-3xl`}>
      <article
        data-testid="tutorial-card"
        data-tutorial-id={tutorial.id}
        className="relative flex h-full flex-col justify-between overflow-hidden rounded-3xl p-5"
      >
        {/* corner glow orb */}
        <span
          aria-hidden="true"
          className="pointer-events-none absolute -right-10 -top-10 size-32 rounded-full opacity-40 blur-2xl transition-opacity duration-500 group-hover:opacity-80"
          style={{ background: "var(--kr-tone)" }}
        />
        <div className="relative">
          <div className="mb-4 flex items-center justify-between gap-2">
            <TargetBadge target={tutorial.target} />
            <div data-testid="tutorial-card-status" data-status={tutorial.status}>
              <TutorialStatusBadge
                status={tutorial.status}
                onInspectDiff={onInspectDiff ? () => onInspectDiff(tutorial) : undefined}
                diffHref={
                  tutorial.status === "auto-updated"
                    ? `/tutorials/${encodeURIComponent(tutorial.id)}?view=diff`
                    : undefined
                }
              />
            </div>
          </div>

          <h3 className="kr-display line-clamp-2 text-lg font-bold leading-snug text-white transition-colors">
            {tutorial.title}
          </h3>

          {tutorial.snippet ? (
            <p data-testid="tutorial-snippet" className="mt-2 line-clamp-2 text-sm leading-relaxed text-ink-300">
              {tutorial.matchStep ? <span className="font-mono text-xs text-ink-400">{t("card.matchStep", { step: tutorial.matchStep })} </span> : null}
              <MarkedText text={tutorial.snippet} />
            </p>
          ) : tutorial.description ? (
            <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-ink-300">{tutorial.description}</p>
          ) : tutorial.taskPrompt ? (
            <p className="mt-2 line-clamp-2 text-sm italic text-ink-400">{t("card.quoted", { text: tutorial.taskPrompt })}</p>
          ) : null}
        </div>

        <div className="relative mt-5 border-t border-white/10 pt-4">
          <div
            data-testid="tutorial-card-meta"
            className="mb-4 flex items-center justify-between text-xs text-ink-300"
          >
            <span className="flex items-center gap-1.5 font-semibold">
              <Layers className="size-3.5" style={{ color: "var(--kr-tone)" }} aria-hidden="true" />
              {t("card.meta", { count: tutorial.stepCount, duration: durationLabel })}
            </span>
            <span className="flex items-center gap-1 text-ink-400">
              <Clock className="size-3" aria-hidden="true" />
              {dateLabel}
            </span>
          </div>

          <Link
            href={`/tutorials/${tutorial.id}`}
            data-testid="tutorial-card-open"
            className="kr-btn kr-btn-tone w-full px-3.5 py-2.5 text-xs"
          >
            <span>{t("card.open")}</span>
            <ArrowUpRight
              aria-hidden="true"
              className="size-4 transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
            />
          </Link>
        </div>
      </article>
    </TiltCard>
  );
}
