import Link from "next/link";
import { ArrowRight, Eye, Fingerprint, Radar, ShieldAlert, Sparkles, Wand2 } from "lucide-react";
import { ApiStatus } from "@/components/api-status";
import { HeroRunDemo } from "@/components/landing/HeroRunDemo";
import { Logo, Reveal, STAGE, ThemeToggle, TiltCard } from "@/components/ui";
import type { ApiClient } from "@/lib/api";

export interface LandingPageProps {
  /** Signed-in visitors get "Open Krama" instead of "Sign in". */
  signedIn?: boolean;
  client?: ApiClient;
}

const STEPS = [
  {
    stage: STAGE.ask,
    title: "Ask",
    text: "Write what you want to learn, e.g. “Show me how to create a GitHub repository”.",
  },
  {
    stage: STAGE.approve,
    title: "Approve the plan",
    text: "Krama lists every step first. Nothing runs until you approve it.",
  },
  {
    stage: STAGE.run,
    title: "Watch it done",
    text: "Krama does the task in a real browser and checks that every step worked.",
  },
  {
    stage: STAGE.learn,
    title: "Learn from the tutorial",
    text: "Replay it step by step with narration, highlights and zoom, at your own pace.",
  },
];

const SIGNALS = [
  { text: "url matches /new", color: "var(--run)" },
  { text: "button “Create” visible", color: "var(--verify)" },
  { text: "POST → 302 redirect", color: "var(--plan)" },
  { text: "field value = bench-new", color: "var(--approve)" },
  { text: "checkbox [checked]", color: "var(--ask)" },
  { text: "password masked ***", color: "var(--learn)" },
  { text: "confidence 1.0", color: "var(--verify)" },
  { text: "destructive step → paused", color: "var(--danger)" },
];

const FEATURES = [
  {
    icon: Eye,
    tone: "kr-run",
    title: "Done on the real site",
    text: "Krama drives a real browser on the real website, so the tutorial shows exactly what you will see.",
    span: "sm:col-span-2",
  },
  {
    icon: Fingerprint,
    tone: "kr-verify",
    title: "Every step checked",
    text: "After each step Krama checks the page really changed, so a tutorial never teaches a step that failed.",
    span: "",
  },
  {
    icon: Wand2,
    tone: "kr-learn",
    title: "Interactive replay",
    text: "Step-by-step guides with narration, captions, highlights and zoom. Passwords and private fields are masked.",
    span: "",
  },
  {
    icon: ShieldAlert,
    tone: "kr-danger",
    title: "Hands off the red button",
    text: "Deleting, transferring or publishing always waits for your OK, right before the click. CAPTCHAs stop the run.",
    span: "",
  },
  {
    icon: Radar,
    tone: "kr-approve",
    title: "Tutorials that notice change",
    text: "Krama re-checks saved tutorials, heals renamed buttons and flags flows that changed.",
    span: "",
  },
];

/** The public landing page for visitors who aren't signed in (#318). */
export function LandingPage({ signedIn = false, client }: LandingPageProps = {}) {
  const primary = signedIn ? { href: "/", label: "Open Krama" } : { href: "/login", label: "Sign in" };

  return (
    <div className="relative flex min-h-screen flex-col text-foreground">
      {/* Floating navigation */}
      <header className="sticky top-3 z-40 mx-auto mt-3 w-[min(72rem,calc(100%-1.5rem))]">
        <div className="kr-glass flex h-14 items-center justify-between gap-3 rounded-full px-3 pl-4">
          <div className="flex items-center gap-3">
            <Link href="/" aria-label="Krama home">
              <Logo size={30} />
            </Link>
            <span className="kr-chip kr-ask hidden sm:inline-flex">
              <Sparkles aria-hidden="true" className="size-3" /> Verified UI Tutorial Engine
            </span>
          </div>
          <nav className="flex items-center gap-2 text-sm font-medium sm:gap-4">
            <ThemeToggle />
            <a href="#how-it-works" className="hidden text-ink-300 transition-colors hover:text-white sm:inline">
              How it works
            </a>
            <Link href={primary.href} data-testid="landing-primary-nav" className="kr-btn kr-btn-primary px-4 py-1.5 text-xs">
              {primary.label}
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-24 px-4 pb-20 pt-14 sm:px-6 sm:pt-20">
        {/* Hero */}
        <section className="grid items-center gap-12 lg:grid-cols-[1.15fr_1fr]">
          <div className="kr-rise flex flex-col items-start">
            <span className="kr-chip kr-verify">
              <span className="kr-dot kr-dot-live !size-2" />
              Recorded and checked on real websites
            </span>

            <h1
              aria-label="Interactive Tutorials Recorded From Real UI Actions"
              className="kr-display mt-6 text-5xl font-extrabold leading-[0.95] text-white sm:text-6xl lg:text-7xl">
              <span className="block">Interactive Tutorials </span>
              <span className="block text-ink-300">Recorded From </span>
              <span className="kr-gradient-text kr-glitch block pb-2">Real UI Actions</span>
            </h1>

            <p className="mt-6 max-w-xl text-lg text-ink-300">
              Tell Krama what you want to learn. It plans the steps, does the task in a real browser, checks every
              step, and turns it into an interactive guide with narration and focal zoom.
            </p>

            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Link href={primary.href} data-testid="landing-primary-cta" className="kr-btn kr-btn-primary px-6 py-3 text-sm">
                {signedIn ? "Open Krama" : "Sign in to start"}
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
              <a href="#how-it-works" className="kr-btn kr-btn-ghost kr-approve px-6 py-3 text-sm">
                See how it works
              </a>
            </div>

            <div className="mt-10 flex items-center gap-6 text-sm">
              <Stat value="0" label="fake UIs" color="var(--ask)" />
              <Stat value="100%" label="steps checked" color="var(--verify)" />
              <Stat value="1" label="click to replay" color="var(--run)" />
            </div>
          </div>

          <div className="kr-rise [animation-delay:150ms]">
            <HeroRunDemo />
          </div>
        </section>

        {/* Evidence marquee */}
        <section aria-label="What Krama checks" className="-mx-4 overflow-hidden sm:-mx-6">
          <div className="kr-rail mb-6 opacity-70" />
          <div className="flex w-max kr-marquee gap-3 [mask-image:linear-gradient(90deg,transparent,#000_10%,#000_90%,transparent)]">
            {[...SIGNALS, ...SIGNALS].map((signal, i) => (
              <span
                key={i}
                className="inline-flex items-center gap-2 whitespace-nowrap rounded-full border border-white/10 bg-white/[0.04] px-4 py-2 font-mono text-xs text-ink-300"
              >
                <span className="size-2 rounded-full" style={{ background: signal.color, boxShadow: `0 0 10px ${signal.color}` }} />
                {signal.text}
              </span>
            ))}
          </div>
        </section>

        {/* Feature bento */}
        <section className="grid grid-cols-1 gap-4 sm:grid-cols-3">
          {FEATURES.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <Reveal key={feature.title} delay={i * 80} className={feature.span}>
                <TiltCard className={`${feature.tone} kr-tone-card group h-full rounded-3xl p-6`}>
                  <div
                    className="flex size-12 items-center justify-center rounded-2xl text-oncolor transition-transform duration-500 group-hover:rotate-12 group-hover:scale-110"
                    style={{ background: "var(--kr-tone)", boxShadow: "0 10px 30px -8px var(--kr-tone)" }}
                  >
                    <Icon aria-hidden="true" className="size-6" />
                  </div>
                  <h2 className="kr-display mt-5 text-xl font-bold text-white">{feature.title}</h2>
                  <p className="mt-2 text-sm leading-relaxed text-ink-300">{feature.text}</p>
                </TiltCard>
              </Reveal>
            );
          })}
        </section>

        {/* How it works */}
        <section id="how-it-works" className="relative scroll-mt-24">
          <Reveal className="mb-10 flex flex-col items-center gap-3 text-center">
            <span className="kr-chip kr-plan">From a question to a tutorial in about a minute</span>
            <h2 className="kr-display text-4xl font-extrabold text-white sm:text-5xl">How it works</h2>
          </Reveal>

          <div className="relative">
            <div className="kr-rail absolute left-0 right-0 top-7 hidden lg:block" aria-hidden="true" />
            <ol className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
              {STEPS.map((step, i) => {
                const Icon = step.stage.icon;
                return (
                  <li key={step.title} className="relative">
                    <Reveal delay={i * 120} className="flex flex-col items-center text-center">
                      <span
                        className="relative z-10 flex size-14 items-center justify-center rounded-full border-4 border-ink-950 text-oncolor"
                        style={{ background: step.stage.color, boxShadow: `0 0 34px ${step.stage.color}` }}
                      >
                        <Icon aria-hidden="true" className="size-6" />
                      </span>
                      <span className="mt-4 font-mono text-xs" style={{ color: step.stage.color }}>
                        0{i + 1}
                      </span>
                      <h3 className="kr-display mt-1 text-lg font-bold text-white">{step.title}</h3>
                      <p className="mt-2 max-w-60 text-sm text-ink-300">{step.text}</p>
                    </Reveal>
                  </li>
                );
              })}
            </ol>
          </div>

          <Reveal className="mt-14 flex justify-center">
            <div className="kr-spectrum-border w-full max-w-3xl rounded-[2rem] bg-ink-900/80 px-6 py-10 text-center">
              <p className="kr-display text-3xl font-extrabold text-white sm:text-4xl">
                Stop reading stale docs. <span className="kr-gradient-text">Watch it done.</span>
              </p>
              <Link href={primary.href} className="kr-btn kr-btn-primary mt-6 px-7 py-3 text-sm">
                {signedIn ? "Make a tutorial" : "Sign in to try it"}
                <ArrowRight aria-hidden="true" className="size-4" />
              </Link>
            </div>
          </Reveal>
        </section>
      </main>

      <footer className="mt-auto border-t border-white/10 bg-ink-950/60 py-8 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-4 sm:flex-row sm:px-6">
          <div className="flex flex-col items-center gap-2 sm:items-start">
            <Logo size={24} />
            <p className="text-xs text-ink-400">Krama &bull; Verified interactive tutorials</p>
            <div className="flex items-center gap-4 text-xs text-ink-400">
              <a href="#how-it-works" className="hover:text-white">
                How it works
              </a>
              <Link href={primary.href} className="hover:text-white">
                {primary.label}
              </Link>
            </div>
          </div>
          <ApiStatus client={client} />
        </div>
      </footer>
    </div>
  );
}

function Stat({ value, label, color }: { value: string; label: string; color: string }) {
  return (
    <div className="flex flex-col">
      <span className="kr-display text-3xl font-extrabold" style={{ color, textShadow: `0 0 24px ${color}` }}>
        {value}
      </span>
      <span className="text-xs uppercase tracking-wider text-ink-400">{label}</span>
    </div>
  );
}
