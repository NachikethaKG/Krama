import Link from "next/link";
import { ArrowLeft, Unlink } from "lucide-react";

export interface RevokedLinkNoticeProps {
  status?: number;
  message?: string;
}

export function RevokedLinkNotice({
  status = 404,
  message = "This tutorial link is invalid or has been revoked by the creator.",
}: RevokedLinkNoticeProps) {
  return (
    <div
      data-testid="revoked-link-notice"
      className="flex min-h-[60vh] w-full flex-col items-center justify-center px-4 py-16 text-center"
    >
      <div className="kr-danger kr-tone-card kr-rise mx-auto flex max-w-md flex-col items-center rounded-[2rem] p-9">
        <div
          className="kr-float mb-5 flex size-16 items-center justify-center rounded-2xl text-ink-950"
          style={{ background: "var(--danger)", boxShadow: "0 0 40px -6px var(--danger)" }}
        >
          <Unlink aria-hidden="true" className="size-8" />
        </div>

        <span className="mb-2 font-mono text-xs font-bold uppercase tracking-[0.2em] text-danger">
          {status === 404 ? "Link Not Found (404)" : `Unavailable (${status})`}
        </span>

        <h1 className="kr-display text-3xl font-extrabold text-white">Tutorial Link Unavailable</h1>

        <p className="mt-3 text-sm text-ink-300">{message}</p>

        <p className="mt-1 text-xs text-ink-400">
          This tutorial may have been removed, or the share link was revoked by the creator.
        </p>

        <div className="mt-7 flex items-center gap-3">
          <Link href="/" data-testid="revoked-home-link" className="kr-btn kr-btn-primary px-5 py-2.5 text-sm">
            <ArrowLeft aria-hidden="true" className="size-4" />
            Return to Homepage
          </Link>
        </div>
      </div>
    </div>
  );
}
