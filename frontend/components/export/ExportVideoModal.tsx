"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Download,
  Film,
  FileText,
  Loader2,
  Monitor,
  RefreshCw,
  Smartphone,
  X,
} from "lucide-react";
import { useTranslations } from "next-intl";
import type { Export, ExportPreset } from "@krama/contracts-ts";
import { getApiClient } from "@/lib/api";

export interface ExportVideoModalProps {
  isOpen: boolean;
  onClose: () => void;
  workflowId: string;
  tutorialTitle?: string;
  stepCount?: number;
}

function formatBytes(bytes?: number | null): string {
  if (!bytes || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

function formatDuration(ms?: number | null): string {
  if (!ms || ms <= 0) return "0s";
  const seconds = Math.round(ms / 1000);
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes > 0) {
    return `${minutes}m ${remainingSeconds}s`;
  }
  return `${seconds}s`;
}

export function ExportVideoModal({
  isOpen,
  onClose,
  workflowId,
  tutorialTitle,
  stepCount = 1,
}: ExportVideoModalProps) {
  const t = useTranslations("export");
  const [preset, setPreset] = useState<ExportPreset>("landscape");
  const [currentExport, setCurrentExport] = useState<Export | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  // The server's message, or which of our own messages to show (translated when shown).
  const [error, setError] = useState<{ message: string | null; fallback: "statusFailed" | "startFailed" } | null>(null);

  const pollTimerRef = useRef<NodeJS.Timeout | null>(null);

  const currentExportId = currentExport?.id;
  const currentExportStatus = currentExport?.status;

  // Poll status while queued or rendering
  useEffect(() => {
    if (!isOpen || !currentExportId) return;
    const isPending = currentExportStatus === "queued" || currentExportStatus === "rendering";
    if (!isPending) return;

    let isCancelled = false;

    pollTimerRef.current = setInterval(async () => {
      try {
        const updated = await getApiClient().getExport(currentExportId);
        if (isCancelled) return;
        setCurrentExport(updated);
        if (updated.status !== "queued" && updated.status !== "rendering") {
          if (pollTimerRef.current) clearInterval(pollTimerRef.current);
        }
      } catch (err) {
        if (isCancelled) return;
        setError({ message: err instanceof Error ? err.message : null, fallback: "statusFailed" });
        if (pollTimerRef.current) clearInterval(pollTimerRef.current);
      }
    }, 2000);

    return () => {
      isCancelled = true;
      if (pollTimerRef.current) {
        clearInterval(pollTimerRef.current);
      }
    };
  }, [isOpen, currentExportId, currentExportStatus]);

  if (!isOpen) return null;

  const handleStartExport = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const exp = await getApiClient().createExport(workflowId, preset);
      setCurrentExport(exp);
    } catch (err: unknown) {
      setError({ message: err instanceof Error ? err.message : null, fallback: "startFailed" });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleReset = () => {
    setCurrentExport(null);
    setError(null);
  };

  const isRendering =
    currentExport && (currentExport.status === "queued" || currentExport.status === "rendering");
  const isReady = currentExport?.status === "ready";
  const isFailed = currentExport?.status === "failed";
  const isExpired = currentExport?.status === "expired";

  const downloadUrl = currentExport?.id
    ? getApiClient().getExportDownloadUrl(currentExport.id)
    : undefined;
  const captionsUrl = currentExport?.id
    ? getApiClient().getExportCaptionsUrl(currentExport.id)
    : undefined;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="export-dialog-title"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-950/80 backdrop-blur-sm animate-fade-in"
    >
      <div className="kr-card relative w-full max-w-lg border border-ink-700 bg-ink-900 p-6 shadow-2xl rounded-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-ink-800 pb-4">
          <div className="flex items-center gap-2.5">
            <div className="flex size-9 items-center justify-center rounded-xl bg-accent/15 text-accent border border-accent/20">
              <Film className="size-5" />
            </div>
            <div>
              <h2 id="export-dialog-title" className="kr-display text-lg font-bold text-white">
                {t("modal.title")}
              </h2>
              <p className="text-xs text-ink-300">
                {tutorialTitle || t("modal.subtitleFallback")}
              </p>
            </div>
          </div>
          <button
            type="button"
            data-testid="close-export-modal-btn"
            onClick={onClose}
            className="rounded-lg p-1.5 text-ink-400 hover:bg-ink-800 hover:text-white transition-colors"
            aria-label={t("modal.closeDialog")}
          >
            <X className="size-5" />
          </button>
        </div>

        {/* Content */}
        <div className="mt-5 space-y-5">
          {error && (
            <div
              data-testid="export-error-banner"
              className="flex items-start gap-3 rounded-xl border border-fail/30 bg-fail/10 p-3.5 text-xs text-fail"
            >
              <AlertCircle className="size-4 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold">{t("modal.errorTitle")}</p>
                <p className="mt-0.5 text-ink-200">{error.message ?? t(`modal.${error.fallback}`)}</p>
              </div>
            </div>
          )}

          {/* 1. Initial State: Preset Selection */}
          {!currentExport && (
            <>
              <div>
                <label className="block text-xs font-semibold uppercase tracking-wider text-ink-300 mb-2.5">
                  {t("modal.selectPreset")}
                </label>
                <div className="grid grid-cols-2 gap-3" role="radiogroup" aria-label={t("modal.presetGroup")}>
                  {/* Landscape option */}
                  <button
                    type="button"
                    role="radio"
                    aria-checked={preset === "landscape"}
                    data-testid="preset-landscape-btn"
                    onClick={() => setPreset("landscape")}
                    className={`flex flex-col items-start gap-2.5 rounded-xl border p-4 text-left transition-all ${
                      preset === "landscape"
                        ? "border-accent bg-accent/10 shadow-sm shadow-accent/20"
                        : "border-ink-800 bg-ink-950/60 hover:border-ink-700"
                    }`}
                  >
                    <div className="flex w-full items-center justify-between">
                      <Monitor className={`size-5 ${preset === "landscape" ? "text-accent" : "text-ink-400"}`} />
                      <span className="font-mono text-xs text-ink-400">16:9</span>
                    </div>
                    <div>
                      <p className="text-sm font-bold text-white">{t("modal.landscape")}</p>
                      <p className="text-xs text-ink-300 mt-0.5">{t("modal.landscapeHint")}</p>
                    </div>
                  </button>

                  {/* Portrait option */}
                  <button
                    type="button"
                    role="radio"
                    aria-checked={preset === "portrait"}
                    data-testid="preset-portrait-btn"
                    onClick={() => setPreset("portrait")}
                    className={`flex flex-col items-start gap-2.5 rounded-xl border p-4 text-left transition-all ${
                      preset === "portrait"
                        ? "border-accent bg-accent/10 shadow-sm shadow-accent/20"
                        : "border-ink-800 bg-ink-950/60 hover:border-ink-700"
                    }`}
                  >
                    <div className="flex w-full items-center justify-between">
                      <Smartphone className={`size-5 ${preset === "portrait" ? "text-accent" : "text-ink-400"}`} />
                      <span className="font-mono text-xs text-ink-400">9:16</span>
                    </div>
                    <div>
                      <p className="text-sm font-bold text-white">{t("modal.portrait")}</p>
                      <p className="text-xs text-ink-300 mt-0.5">{t("modal.portraitHint")}</p>
                    </div>
                  </button>
                </div>
              </div>

              {/* Feature Highlights */}
              <div className="rounded-xl border border-ink-800 bg-ink-950/40 p-3.5 text-xs text-ink-300 space-y-1.5 font-mono">
                <p className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-approve" />
                  <span>{t("modal.featureVoice")}</span>
                </p>
                <p className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-learn" />
                  <span>{t("modal.featureCaptions")}</span>
                </p>
                <p className="flex items-center gap-2">
                  <span className="size-1.5 rounded-full bg-accent" />
                  <span>{t("modal.featureChapters", { count: stepCount })}</span>
                </p>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  data-testid="cancel-export-btn"
                  onClick={onClose}
                  className="kr-btn kr-btn-secondary px-4 py-2 text-sm text-ink-300 hover:text-white"
                >
                  {t("modal.cancel")}
                </button>
                <button
                  type="button"
                  data-testid="start-export-btn"
                  disabled={isSubmitting}
                  onClick={handleStartExport}
                  className="kr-btn kr-btn-primary flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-accent hover:bg-accent/90"
                >
                  {isSubmitting ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      <span>{t("modal.queueing")}</span>
                    </>
                  ) : (
                    <>
                      <Film className="size-4" />
                      <span>{t("modal.start")}</span>
                    </>
                  )}
                </button>
              </div>
            </>
          )}

          {/* 2. Rendering / In-Progress State */}
          {isRendering && (
            <div data-testid="export-rendering-container" className="py-4 space-y-4 text-center">
              <div className="flex justify-center">
                <div className="relative flex size-16 items-center justify-center rounded-2xl bg-accent/10 border border-accent/30 text-accent">
                  <Loader2 className="size-8 animate-spin" />
                </div>
              </div>

              <div>
                <h3 className="text-base font-bold text-white">
                  {currentExport.status === "queued" ? t("modal.queued") : t("modal.rendering")}
                </h3>
                <p className="text-xs text-ink-300 mt-1">
                  {t("modal.renderingHint")}
                </p>
              </div>

              {/* Progress bar */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between text-xs font-mono text-ink-300">
                  <span>{currentExport.progress < 15 ? t("modal.phaseVoice") : t("modal.phaseFrames")}</span>
                  <span data-testid="export-progress-percent">{currentExport.progress}%</span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-ink-800">
                  <div
                    data-testid="export-progress-bar"
                    className="h-full bg-gradient-to-r from-accent to-learn transition-all duration-300 ease-out"
                    style={{ width: `${currentExport.progress}%` }}
                  />
                </div>
              </div>

              <p className="font-mono text-[11px] text-ink-400">
                {t("modal.presetLine", { preset: currentExport.preset === "portrait" ? t("modal.portraitRatio") : t("modal.landscapeRatio") })}
              </p>
            </div>
          )}

          {/* 3. Ready / Finished State */}
          {isReady && (
            <div data-testid="export-ready-container" className="py-2 space-y-4">
              <div className="flex items-center gap-3 rounded-xl border border-approve/30 bg-approve/10 p-3.5 text-xs text-approve">
                <CheckCircle2 className="size-5 shrink-0" />
                <div>
                  <p className="font-bold text-sm">{t("modal.completeTitle")}</p>
                  <p className="mt-0.5 text-ink-200">
                    {t("modal.completeBody")}
                  </p>
                </div>
              </div>

              {/* Video stats */}
              <div className="grid grid-cols-3 gap-2.5 rounded-xl border border-ink-800 bg-ink-950/60 p-3 text-center font-mono text-xs">
                <div>
                  <span className="text-ink-400 text-[10px] uppercase">{t("modal.statDuration")}</span>
                  <p className="font-bold text-white mt-0.5">{formatDuration(currentExport.duration_ms)}</p>
                </div>
                <div>
                  <span className="text-ink-400 text-[10px] uppercase">{t("modal.statSize")}</span>
                  <p className="font-bold text-white mt-0.5">{formatBytes(currentExport.size_bytes)}</p>
                </div>
                <div>
                  <span className="text-ink-400 text-[10px] uppercase">{t("modal.statPreset")}</span>
                  <p className="font-bold text-white mt-0.5 capitalize">
                    {currentExport.preset === "portrait" ? t("modal.portrait") : t("modal.landscape")}
                  </p>
                </div>
              </div>

              {/* Download actions */}
              <div className="space-y-2 pt-2">
                {downloadUrl && (
                  <a
                    href={downloadUrl}
                    download
                    data-testid="download-video-btn"
                    className="kr-btn kr-btn-primary flex w-full items-center justify-center gap-2 py-2.5 text-sm font-semibold text-white bg-accent hover:bg-accent/90"
                  >
                    <Download className="size-4" />
                    <span>{t("modal.downloadVideo")}</span>
                  </a>
                )}

                {captionsUrl && (
                  <a
                    href={captionsUrl}
                    download
                    data-testid="download-captions-btn"
                    className="kr-btn kr-btn-secondary flex w-full items-center justify-center gap-2 py-2 text-xs text-ink-300 hover:text-white border border-ink-700"
                  >
                    <FileText className="size-3.5 text-learn" />
                    <span>{t("modal.downloadCaptions")}</span>
                  </a>
                )}

                <button
                  type="button"
                  data-testid="export-another-btn"
                  onClick={handleReset}
                  className="flex w-full items-center justify-center gap-1.5 text-xs text-ink-400 hover:text-ink-200 pt-2 transition-colors"
                >
                  <RefreshCw className="size-3" />
                  <span>{t("modal.exportAnother")}</span>
                </button>
              </div>
            </div>
          )}

          {/* 4. Failed / Expired State */}
          {(isFailed || isExpired) && (
            <div data-testid="export-failed-container" className="py-2 space-y-4">
              <div className="flex items-start gap-3 rounded-xl border border-fail/30 bg-fail/10 p-3.5 text-xs text-fail">
                <AlertCircle className="size-5 shrink-0 mt-0.5" />
                <div>
                  <p className="font-bold text-sm">
                    {isExpired ? t("modal.expiredTitle") : t("modal.failedTitle")}
                  </p>
                  <p className="mt-0.5 text-ink-200">
                    {currentExport.error?.message ||
                      (isExpired ? t("modal.expiredBody") : t("modal.failedBody"))}
                  </p>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={onClose}
                  className="kr-btn kr-btn-secondary px-4 py-2 text-sm text-ink-300 hover:text-white"
                >
                  {t("modal.close")}
                </button>
                <button
                  type="button"
                  data-testid="retry-export-btn"
                  onClick={handleReset}
                  className="kr-btn kr-btn-primary flex items-center gap-2 px-5 py-2 text-sm font-semibold text-white bg-accent hover:bg-accent/90"
                >
                  <RefreshCw className="size-4" />
                  <span>{t("modal.tryAgain")}</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
