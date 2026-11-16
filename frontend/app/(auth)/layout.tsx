import type { ReactNode } from "react";
import Link from "next/link";
import { Logo, STAGES } from "@/components/ui";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative grid min-h-screen lg:grid-cols-2">
      {/* Left: the spectrum story, on large screens only */}
      <aside aria-hidden="true" className="relative hidden flex-col justify-between overflow-hidden p-12 lg:flex">
        <Logo size={38} />
        <div>
          <p className="kr-display text-6xl font-extrabold leading-[0.95] text-white">
            Ask it.
            <br />
            <span className="kr-gradient-text">Watch it done.</span>
            <br />
            Learn it.
          </p>
          <div className="mt-10 flex flex-col gap-3">
            {STAGES.map((stage, i) => {
              const Icon = stage.icon;
              return (
                <div
                  key={stage.key}
                  className="kr-rise flex items-center gap-3"
                  style={{ animationDelay: `${200 + i * 90}ms` }}
                >
                  <span
                    className="flex size-9 items-center justify-center rounded-xl text-ink-950"
                    style={{ background: stage.color, boxShadow: `0 0 20px -2px ${stage.color}` }}
                  >
                    <Icon className="size-4" />
                  </span>
                  <span className="font-semibold text-white">{stage.verb}</span>
                  <span className="text-sm text-ink-400">{stage.blurb}</span>
                </div>
              );
            })}
          </div>
        </div>
        <div className="kr-rail w-40" />
      </aside>

      {/* Right: the form */}
      <div className="flex flex-col justify-center px-4 py-12 sm:px-6 lg:px-16">
        <div className="sm:mx-auto sm:w-full sm:max-w-md">
          <Link href="/" className="flex justify-center lg:hidden" aria-label="Krama home">
            <Logo size={36} />
          </Link>
        </div>
        <div className="kr-rise mt-8 sm:mx-auto sm:w-full sm:max-w-md">{children}</div>
      </div>
    </div>
  );
}
