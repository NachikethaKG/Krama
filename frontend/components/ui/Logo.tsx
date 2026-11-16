/** Krama's mark: a "K" set on a spinning spectrum ring, with the wordmark beside it. */
export function LogoMark({ size = 34 }: { size?: number }) {
  return (
    <span
      className="kr-spectrum-border relative inline-flex shrink-0 items-center justify-center rounded-xl bg-ink-900"
      style={{ width: size, height: size }}
    >
      <span className="kr-display kr-gradient-text text-lg font-extrabold leading-none" style={{ fontSize: size * 0.55 }}>
        K
      </span>
    </span>
  );
}

export function Logo({ size = 34, showWord = true }: { size?: number; showWord?: boolean }) {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark size={size} />
      {showWord && (
        <span className="kr-display text-xl font-extrabold tracking-tight text-white">
          krama<span className="text-ask">.</span>
        </span>
      )}
    </span>
  );
}
