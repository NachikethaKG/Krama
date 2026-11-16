/** The player paints each step in the next colour of the Krama spectrum, so a tutorial reads as a sequence. */
export const SPECTRUM = [
  "var(--ask)",
  "var(--plan)",
  "var(--approve)",
  "var(--run)",
  "var(--verify)",
  "var(--learn)",
] as const;

export function stepColor(index: number): string {
  const i = ((index % SPECTRUM.length) + SPECTRUM.length) % SPECTRUM.length;
  return SPECTRUM[i];
}
