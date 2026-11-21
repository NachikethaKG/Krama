"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, Loader2, PauseCircle, Play, UserRound, X, Zap } from "lucide-react";
import { useTranslations } from "next-intl";
import type { Workflow, WorkflowInputList } from "@krama/contracts-ts";
import { type ApiClient, errorMessage, getApiClient, inputProblem, isApiError } from "@/lib/api";

export interface DoItForMeModalProps {
  isOpen: boolean;
  onClose: () => void;
  workflowId: string;
  tutorialTitle?: string;
  client?: ApiClient;
}

type Loaded =
  | { state: "loading" }
  | { state: "refused"; cause: unknown }
  | { state: "ready"; list: WorkflowInputList; workflow: Workflow };

/** Formats one "doIt" namespace message: pass the component's `useTranslations("doIt")`. */
export type DoItText = (key: string, values?: Record<string, string | number>) => string;

/** Why the workflow can't run for the user, in plain words (409 reasons in docs/api-contract.md). */
export function refusalMessage(err: unknown, t: DoItText): string {
  const details = isApiError(err) ? err.details : undefined;
  switch (details?.reason) {
    case "not_verified":
      return t("refusal.notVerified");
    case "pending_review":
      return t("refusal.pendingReview");
    case "secret_not_stored": {
      const step =
        typeof details.step_seq === "number" ? t("refusal.stepN", { step: details.step_seq }) : t("refusal.aStep");
      return t("refusal.secretNotStored", { step });
    }
    case "stale_revision":
      return t("refusal.staleRevision");
    case "site_sign_in_needed":
      return t("refusal.signInNeeded", { site: String(details.site ?? t("refusal.theSite")) });
    default:
      if (isApiError(err) && err.apiMessage) return err.apiMessage;
      return errorMessage(err, t("refusal.fallback"));
  }
}

/** The step text with each example swapped for the user's value (whole words only), for the preview. */
export function previewText(text: string, swaps: Record<string, string>): string {
  let out = text;
  for (const [example, value] of Object.entries(swaps)) {
    if (!example || !value || example === value) continue;
    const escaped = example.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    out = out.replace(new RegExp(`(?<![A-Za-z0-9])${escaped}(?![A-Za-z0-9])`, "g"), value);
  }
  return out;
}

/**
 * "Do it for me" (#129, #402): the owner types their own values, sees the steps with them, then Krama runs the
 * stored workflow. Starting it is the approval; risky steps still pause in the live view (P6). A failed step
 * stops the run (P7).
 */
export function DoItForMeModal({ isOpen, ...props }: DoItForMeModalProps) {
  // Mounted only while open, so every opening starts with empty values.
  return isOpen ? <DoItForMeDialog {...props} /> : null;
}

function DoItForMeDialog({ onClose, workflowId, tutorialTitle, client }: Omit<DoItForMeModalProps, "isOpen">) {
  const t = useTranslations("doIt");
  const router = useRouter();
  const api = useMemo(() => client ?? getApiClient(), [client]);
  const [loaded, setLoaded] = useState<Loaded>({ state: "loading" });
  const [values, setValues] = useState<Record<string, string>>({});
  const [serverErrors, setServerErrors] = useState<Record<string, string>>({});
  const [touched, setTouched] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [list, workflow] = await Promise.all([api.getWorkflowInputs(workflowId), api.getWorkflow(workflowId)]);
        if (!cancelled) setLoaded({ state: "ready", list, workflow });
      } catch (err) {
        if (!cancelled) setLoaded({ state: "refused", cause: err });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, workflowId]);

  const inputs = loaded.state === "ready" ? loaded.list.inputs : [];
  const problems: Record<string, string | null> = Object.fromEntries(
    inputs.map((i) => [i.key, serverErrors[i.key] ?? inputProblem(i, values[i.key])]),
  );
  const canRun = loaded.state === "ready" && inputs.every((i) => problems[i.key] === null) && !submitting;
  const swaps = Object.fromEntries(inputs.map((i) => [i.example, values[i.key] ?? ""]));

  const signIn = async (site: string) => {
    setError(null);
    try {
      const run = await api.startSignIn(site);
      router.push(`/runs/${encodeURIComponent(run.id)}/live`);
    } catch (err) {
      setError(refusalMessage(err, t));
    }
  };

  const start = async () => {
    setTouched(true);
    if (loaded.state !== "ready" || !canRun) return;
    setSubmitting(true);
    setError(null);
    try {
      const run = await api.runWorkflow(workflowId, loaded.list.revision, values);
      router.push(`/runs/${encodeURIComponent(run.id)}/live`);
    } catch (err) {
      const details = isApiError(err) ? err.details : undefined;
      if (details?.reason === "input_unsafe" && typeof details.key === "string") {
        const message = isApiError(err) && err.apiMessage ? err.apiMessage : t("modal.valueUnsafe");
        setServerErrors({ [details.key]: message });
      } else {
        setError(refusalMessage(err, t));
      }
      setSubmitting(false);
    }
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="do-it-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/80 p-4 backdrop-blur-sm animate-fade-in"
    >
      <div className="kr-card relative flex max-h-[90vh] w-full max-w-xl flex-col rounded-2xl border border-ink-700 bg-ink-900 p-6 shadow-2xl">
        <div className="flex items-center justify-between border-b border-ink-800 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex size-9 items-center justify-center rounded-xl border border-approve/20 bg-approve/15 text-approve">
              <Zap aria-hidden="true" className="size-5" />
            </div>
            <div>
              <h2 id="do-it-dialog-title" className="kr-display text-lg font-bold text-white">
                {t("modal.title")}
              </h2>
              <p className="text-xs text-ink-300">{tutorialTitle || t("modal.subtitleFallback")}</p>
            </div>
          </div>
          <button
            type="button"
            data-testid="close-do-it-modal-btn"
            onClick={onClose}
            className="rounded-lg p-1.5 text-ink-400 transition-colors hover:bg-ink-800 hover:text-white"
            aria-label={t("modal.closeDialog")}
          >
            <X aria-hidden="true" className="size-5" />
          </button>
        </div>

        <div className="mt-5 flex-1 space-y-5 overflow-y-auto">
          {loaded.state === "loading" && (
            <p role="status" data-testid="do-it-loading" className="flex items-center gap-2 text-sm text-ink-300">
              <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              {t("modal.loading")}
            </p>
          )}

          {loaded.state === "refused" && (
            <p
              role="alert"
              data-testid="do-it-refused"
              className="flex items-start gap-3 rounded-xl border border-fail/30 bg-fail/10 p-3.5 text-sm text-ink-100"
            >
              <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-fail" />
              {refusalMessage(loaded.cause, t)}
            </p>
          )}

          {loaded.state === "ready" && (
            <>
              {loaded.list.sign_in_site ? (
                <div data-testid="do-it-sign-in" className="rounded-xl border border-run/30 bg-run/10 p-3 text-xs text-ink-200">
                  <p className="font-semibold text-white">{t("modal.signInFirst", { site: loaded.list.sign_in_site })}</p>
                  <p className="mt-1">
                    {t("modal.signInHint")}
                  </p>
                  <button
                    type="button"
                    data-testid="do-it-sign-in-btn"
                    onClick={() => signIn(loaded.list.sign_in_site as string)}
                    className="kr-btn kr-btn-tone mt-2 px-3.5 py-1.5 text-xs"
                  >
                    {t("modal.signInButton", { site: loaded.list.sign_in_site })}
                  </button>
                </div>
              ) : (
                <p data-testid="do-it-account" className="flex items-start gap-2 text-xs text-ink-300">
                  <UserRound aria-hidden="true" className="mt-0.5 size-3.5 shrink-0 text-run" />
                  <span>
                    {loaded.list.account
                      ? t.rich("modal.actsInAccount", {
                          account: loaded.list.account,
                          strong: (chunks) => <strong className="text-white">{chunks}</strong>,
                        })
                      : t("modal.actsInSignedIn")}
                  </span>
                </p>
              )}

              {inputs.length > 0 ? (
                <div className="space-y-3">
                  {inputs.map((input) => {
                    const id = `do-it-input-${input.key}`;
                    const problem = problems[input.key];
                    const show = problem && (touched || values[input.key] !== undefined);
                    return (
                      <div key={input.key}>
                        <label htmlFor={id} className="mb-1.5 block text-xs font-semibold text-ink-200">
                          {input.label}
                        </label>
                        <input
                          id={id}
                          data-testid={id}
                          type="text"
                          autoComplete="off"
                          value={values[input.key] ?? ""}
                          placeholder={t("modal.placeholder", { example: input.example })}
                          aria-invalid={show ? true : undefined}
                          aria-describedby={show ? `${id}-error` : undefined}
                          onChange={(e) => {
                            const value = e.target.value;
                            setValues((v) => ({ ...v, [input.key]: value }));
                            setServerErrors((errors) => {
                              const rest = { ...errors };
                              delete rest[input.key];
                              return rest;
                            });
                          }}
                          className="w-full rounded-xl border border-ink-700 bg-ink-950/60 px-3 py-2 text-sm text-white placeholder:text-ink-500 focus:border-approve focus:outline-none"
                        />
                        {show ? (
                          <p id={`${id}-error`} className="mt-1 text-xs text-fail">
                            {problem}
                          </p>
                        ) : null}
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="text-xs text-ink-300">{t("modal.noValues")}</p>
              )}

              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink-300">{t("modal.previewTitle")}</p>
                <ol data-testid="do-it-preview" className="space-y-1.5">
                  {[...loaded.workflow.steps]
                    .sort((a, b) => a.seq - b.seq)
                    .map((s) => (
                      <li
                        key={s.seq}
                        data-testid={`do-it-preview-step-${s.seq}`}
                        className="flex items-start gap-2 rounded-lg border border-ink-800 bg-ink-950/40 px-3 py-2 text-xs text-ink-200"
                      >
                        <span className="font-mono text-ink-400">{s.seq}.</span>
                        <span className="flex-1">{previewText(s.instruction_text, swaps)}</span>
                        {s.risk === "high" ? (
                          <span
                            data-testid={`do-it-pauses-${s.seq}`}
                            className="flex shrink-0 items-center gap-1 rounded-md bg-plan/15 px-1.5 py-0.5 font-semibold text-plan"
                          >
                            <PauseCircle aria-hidden="true" className="size-3" />
                            {t("modal.asksFirst")}
                          </span>
                        ) : null}
                      </li>
                    ))}
                </ol>
                <p className="mt-2 text-[11px] text-ink-400">
                  {t("modal.safetyNote")}
                </p>
              </div>
            </>
          )}

          {error && (
            <p role="alert" data-testid="do-it-error" className="rounded-xl border border-fail/30 bg-fail/10 p-3 text-xs text-ink-100">
              {error}
            </p>
          )}
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-ink-800 pt-4">
          <button type="button" onClick={onClose} className="kr-btn kr-btn-secondary px-4 py-2 text-sm">
            {t("modal.cancel")}
          </button>
          <button
            type="button"
            data-testid="do-it-run-btn"
            disabled={loaded.state !== "ready" || submitting || Boolean(loaded.state === "ready" && loaded.list.sign_in_site)}
            aria-disabled={!canRun}
            onClick={start}
            className="kr-btn kr-btn-primary flex items-center gap-2 px-5 py-2 text-sm font-semibold"
          >
            {submitting ? (
              <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            ) : (
              <Play aria-hidden="true" className="size-4" />
            )}
            {t("modal.run")}
          </button>
        </div>
      </div>
    </div>
  );
}
