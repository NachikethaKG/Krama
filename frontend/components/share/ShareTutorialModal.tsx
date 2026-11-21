"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Link2, Share2, X } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import type { ShareLink } from "@krama/contracts-ts";
import { getApiClient } from "@/lib/api";

export interface ShareTutorialModalProps {
  isOpen: boolean;
  onClose: () => void;
  workflowId: string;
  tutorialTitle?: string;
}

type ErrorKey = "loadFailed" | "createFailed" | "copyFailed" | "revokeFailed";

export function ShareTutorialModal({
  isOpen,
  onClose,
  workflowId,
  tutorialTitle,
}: ShareTutorialModalProps) {
  const t = useTranslations("share");
  const locale = useLocale();
  const [links, setLinks] = useState<ShareLink[]>([]);
  const [activeUrl, setActiveUrl] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [revokingId, setRevokingId] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  // The server's message, or which of our own messages to show (translated when shown).
  const [error, setError] = useState<{ message: string | null; fallback: ErrorKey } | null>(null);

  useEffect(() => {
    if (!isOpen || !workflowId) return;
    let cancelled = false;

    Promise.resolve().then(() => {
      if (cancelled) return;
      setIsLoading(true);
      setError(null);
    });

    getApiClient()
      .listShareLinks(workflowId)
      .then((res) => {
        if (cancelled) return;
        setLinks(res.items || []);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError({ message: err instanceof Error ? err.message : null, fallback: "loadFailed" });
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isOpen, workflowId]);

  if (!isOpen) return null;

  const activeLinks = links.filter(
    (link) => !link.revoked_at && (!link.expires_at || new Date(link.expires_at) > new Date()),
  );

  const handleCreate = async () => {
    setIsCreating(true);
    setError(null);
    try {
      const res = await getApiClient().createShareLink(workflowId);
      setActiveUrl(res.url);
      setLinks((prev) => [res.link, ...prev.filter((l) => l.id !== res.link.id)]);
    } catch (err: unknown) {
      setError({ message: err instanceof Error ? err.message : null, fallback: "createFailed" });
    } finally {
      setIsCreating(false);
    }
  };

  const handleCopy = async () => {
    if (!activeUrl) return;
    try {
      await navigator.clipboard.writeText(activeUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError({ message: null, fallback: "copyFailed" });
    }
  };

  const handleRevoke = async (shareId: string) => {
    setRevokingId(shareId);
    setError(null);
    try {
      const updated = await getApiClient().revokeShareLink(workflowId, shareId);
      setLinks((prev) => prev.map((l) => (l.id === shareId ? updated : l)));
      setActiveUrl(null);
    } catch (err: unknown) {
      setError({ message: err instanceof Error ? err.message : null, fallback: "revokeFailed" });
    } finally {
      setRevokingId(null);
    }
  };

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-ink-950/75 backdrop-blur-md animate-in fade-in duration-200"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="share-modal-title"
        data-testid="share-tutorial-modal"
        className="kr-tone-card relative w-full max-w-lg overflow-hidden rounded-3xl border border-white/10 bg-ink-900/95 p-6 shadow-2xl backdrop-blur-2xl"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-4">
          <div className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-xl bg-approve/15 text-approve">
              <Share2 className="size-4" aria-hidden="true" />
            </span>
            <div>
              <h2 id="share-modal-title" className="kr-display text-lg font-bold text-white">
                {t("modal.title")}
              </h2>
              {tutorialTitle && <p className="text-xs text-ink-400 line-clamp-1">{tutorialTitle}</p>}
            </div>
          </div>
          <button
            type="button"
            data-testid="close-share-modal-btn"
            onClick={onClose}
            className="rounded-lg p-1.5 text-ink-400 hover:bg-white/5 hover:text-white transition-colors"
            aria-label={t("modal.closeDialog")}
          >
            <X className="size-4" />
          </button>
        </div>

        {/* Content */}
        <div className="mt-4 space-y-4">
          {error && (
            <div
              role="alert"
              data-testid="share-modal-error"
              className="rounded-xl border border-danger/40 bg-danger/10 p-3 text-xs text-danger"
            >
              {error.message ?? t(`modal.${error.fallback}`)}
            </div>
          )}

          {isLoading ? (
            <div data-testid="share-modal-loading" className="flex items-center justify-center py-8 text-xs text-ink-400">
              <span className="mr-2 size-4 animate-spin rounded-full border-2 border-white/20 border-t-approve" />
              {t("modal.loading")}
            </div>
          ) : (
            <>
              {/* Newly created or active share URL presentation */}
              {activeUrl ? (
                <div className="space-y-2 rounded-2xl border border-approve/40 bg-approve/5 p-4">
                  <span className="text-[11px] font-bold uppercase tracking-wider text-approve">
                    {t("modal.ready")}
                  </span>
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      readOnly
                      value={activeUrl}
                      data-testid="share-url-input"
                      className="w-full rounded-xl border border-white/10 bg-ink-950 px-3 py-2 font-mono text-xs text-white focus:outline-none"
                    />
                    <button
                      type="button"
                      data-testid="copy-share-url-btn"
                      onClick={handleCopy}
                      className="kr-btn kr-btn-primary shrink-0 px-3 py-2 text-xs"
                    >
                      {copied ? (
                        <>
                          <Check className="size-3.5 mr-1" /> {t("modal.copied")}
                        </>
                      ) : (
                        <>
                          <Copy className="size-3.5 mr-1" /> {t("modal.copyLink")}
                        </>
                      )}
                    </button>
                  </div>
                  <p className="text-[11px] text-ink-400">
                    {t("modal.readyHint")}
                  </p>
                </div>
              ) : activeLinks.length === 0 ? (
                <div className="rounded-2xl border border-white/10 bg-white/[0.02] p-5 text-center">
                  <Link2 className="mx-auto mb-2 size-8 text-ink-400 opacity-60" aria-hidden="true" />
                  <p className="text-xs text-ink-300">{t("modal.emptyTitle")}</p>
                  <p className="mt-1 text-[11px] text-ink-400">
                    {t("modal.emptyHint")}
                  </p>
                </div>
              ) : null}

              {/* Action to create a new link */}
              <div className="flex items-center justify-between pt-1">
                <span className="text-xs text-ink-400">
                  {activeLinks.length > 0 ? t("modal.activeCount", { count: activeLinks.length }) : t("modal.shareLink")}
                </span>
                <button
                  type="button"
                  data-testid="create-share-link-btn"
                  onClick={handleCreate}
                  disabled={isCreating}
                  className="kr-btn kr-btn-tone kr-approve px-3 py-1.5 text-xs"
                >
                  {isCreating ? t("modal.creating") : activeLinks.length > 0 ? t("modal.generateNew") : t("modal.create")}
                </button>
              </div>

              {/* List of existing links with revocation controls */}
              {links.length > 0 && (
                <div className="space-y-2 border-t border-white/10 pt-3">
                  <h4 className="text-[11px] font-bold uppercase tracking-wider text-ink-400">
                    {t("modal.history")}
                  </h4>
                  <ul data-testid="share-links-list" className="space-y-2 max-h-48 overflow-y-auto">
                    {links.map((link) => {
                      const isRevoked = Boolean(link.revoked_at);
                      return (
                        <li
                          key={link.id}
                          data-testid="share-link-item"
                          className="flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.02] p-2.5 text-xs"
                        >
                          <div className="flex flex-col gap-0.5">
                            <span className="font-mono text-[11px] text-ink-300">
                              {t("modal.created", { date: new Date(link.created_at).toLocaleDateString(locale) })}
                            </span>
                            <span className="text-[10px] text-ink-400">
                              {isRevoked ? t("modal.revoked") : t("modal.activeLink")}
                            </span>
                          </div>

                          <div>
                            {isRevoked ? (
                              <span className="kr-chip kr-danger !text-[10px]">{t("modal.revoked")}</span>
                            ) : (
                              <button
                                type="button"
                                data-testid="revoke-share-link-btn"
                                onClick={() => handleRevoke(link.id)}
                                disabled={revokingId === link.id}
                                className="kr-btn kr-btn-ghost kr-danger px-2.5 py-1 text-xs text-danger"
                              >
                                {revokingId === link.id ? t("modal.revoking") : t("modal.revoke")}
                              </button>
                            )}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
