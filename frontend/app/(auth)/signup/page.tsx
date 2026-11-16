import Link from "next/link";
import { ArrowLeft, ArrowRight, KeyRound, LockKeyhole } from "lucide-react";

export const metadata = {
  title: "Registration Access · Krama",
  description: "Public registration is currently closed for the MVP phase.",
};

export default function SignupPage() {
  return (
    <div className="kr-spectrum-border rounded-[2rem] bg-ink-900/85 px-6 py-9 backdrop-blur-xl sm:px-10">
      <div className="mb-6 text-center">
        <div
          className="kr-float mx-auto mb-4 flex size-14 items-center justify-center rounded-2xl text-oncolor"
          style={{ background: "var(--plan)", boxShadow: "0 0 34px -4px var(--plan)" }}
        >
          <LockKeyhole aria-hidden="true" className="size-7" />
        </div>
        <h1 className="kr-display text-3xl font-extrabold text-white">Public Registration Closed</h1>
        <p className="mt-3 text-sm leading-relaxed text-ink-300">
          To protect rate limits and shared automation runners during our early MVP evaluation phase, self-service
          account registration is currently gated.
        </p>
      </div>

      <div className="kr-verify kr-tone-card space-y-3 rounded-2xl p-4">
        <div className="flex items-center gap-2">
          <span className="kr-dot" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-verify">Seeded Evaluation Credentials</h2>
        </div>

        <p className="text-xs text-ink-300">
          Evaluators and usability test participants can sign in using the seeded test account created via the
          repository recipe:
        </p>

        <div className="space-y-1.5 rounded-xl border border-white/10 bg-ink-950/60 p-3 font-mono text-xs">
          <div className="flex justify-between gap-3">
            <span className="text-ink-400">Email:</span>
            <span className="font-semibold text-white">demo@krama.dev</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-ink-400">Password:</span>
            <span className="font-semibold text-white">KRAMA_DEMO_PASSWORD in .env</span>
          </div>
          <div className="flex justify-between gap-3 border-t border-white/10 pt-1.5">
            <span className="text-ink-400">Recipe:</span>
            <span className="flex items-center gap-1 text-ask">
              <KeyRound aria-hidden="true" className="size-3" />
              just seed-users
            </span>
          </div>
        </div>
      </div>

      <div className="mt-6 space-y-3">
        <Link href="/login" data-testid="signup-login-link" className="kr-btn kr-btn-primary w-full px-4 py-3 text-sm">
          <span>Sign In with Seeded Account</span>
          <ArrowRight aria-hidden="true" className="size-4" />
        </Link>

        <Link href="/" className="kr-btn kr-btn-ghost w-full px-4 py-2.5 text-xs">
          <ArrowLeft aria-hidden="true" className="size-3.5" />
          Return to Krama Home
        </Link>
      </div>
    </div>
  );
}
