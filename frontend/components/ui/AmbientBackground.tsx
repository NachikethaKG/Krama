/**
 * The living backdrop behind every page: six drifting aurora blobs (one per pipeline stage), a fading
 * grid and film grain. Pure CSS, fixed behind the content, ignored by pointer and screen readers.
 */
const BLOBS = [
  { color: "var(--ask)", className: "left-[-10%] top-[-12%] size-[42vw]", delay: "0s" },
  { color: "var(--approve)", className: "right-[-12%] top-[5%] size-[38vw]", delay: "-6s" },
  { color: "var(--run)", className: "left-[25%] top-[45%] size-[34vw]", delay: "-12s" },
  { color: "var(--plan)", className: "right-[10%] bottom-[-15%] size-[30vw]", delay: "-3s" },
  { color: "var(--verify)", className: "left-[-8%] bottom-[-10%] size-[26vw]", delay: "-9s" },
  { color: "var(--learn)", className: "right-[35%] top-[-20%] size-[22vw]", delay: "-15s" },
];

export function AmbientBackground() {
  return (
    <>
      <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10 overflow-hidden bg-ink-950">
        {BLOBS.map((blob) => (
          <span
            key={blob.color}
            className={`kr-blob ${blob.className}`}
            style={{
              background: `radial-gradient(circle at 30% 30%, ${blob.color}, transparent 70%)`,
              animationDelay: blob.delay,
              opacity: 0.22,
            }}
          />
        ))}
        <div className="kr-grid-bg absolute inset-0" />
        <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-ink-950 to-transparent" />
      </div>
      <div aria-hidden="true" className="kr-grain" />
    </>
  );
}
