// UNTESTED sketch for the Next.js 16 / React 19 frontend, derived from web/replay.html (which is verified).
'use client';
import { useEffect, useRef } from 'react';
import { Replayer } from 'rrweb';            // module import is SSR-safe; construct only in useEffect
import 'rrweb/dist/style.css';

type Step = { timeOffset: number; bbox: [number, number, number, number] }; // page coords, CSS px

export function ReplayStage({ events, step, width }: { events: any[]; step: Step; width: number }) {
  const root = useRef<HTMLDivElement>(null);
  const rp = useRef<Replayer | null>(null);
  const rect = useRef<SVGRectElement | null>(null);
  const meta = events.find((e) => e.type === 4).data as { width: number; height: number };
  const scale = width / meta.width;

  useEffect(() => {
    const r = new Replayer(events, { root: root.current!, mouseTail: false, skipInactive: false });
    r.wrapper.style.transformOrigin = '0 0';
    // Overlay INSIDE the wrapper: drawn in unscaled recorded-viewport px; the wrapper's transform scales it.
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    Object.assign(svg.style, { position: 'absolute', left: '0', top: '0', pointerEvents: 'none', overflow: 'visible' });
    svg.setAttribute('width', String(meta.width)); svg.setAttribute('height', String(meta.height));
    rect.current = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
    svg.appendChild(rect.current); r.wrapper.appendChild(svg);
    rp.current = r;
    let raf = 0; const loop = () => { draw(); raf = requestAnimationFrame(loop); }; raf = requestAnimationFrame(loop); // follows smooth scroll during play
    return () => { cancelAnimationFrame(raf); r.destroy(); root.current?.replaceChildren(); rp.current = null; }; // StrictMode double-mount safe
  }, [events]);

  const draw = () => {
    const r = rp.current, el = rect.current; if (!r || !el) return;
    const w = r.iframe.contentWindow!; const [x, y, bw, bh] = stepRef.current.bbox;
    el.setAttribute('x', String(x - w.scrollX)); el.setAttribute('y', String(y - w.scrollY));
    el.setAttribute('width', String(bw)); el.setAttribute('height', String(bh));
  };
  const stepRef = useRef(step); stepRef.current = step;

  useEffect(() => { rp.current?.pause(step.timeOffset); draw(); }, [step]);          // pause(t) = seek; scroll applied instantly
  useEffect(() => { if (rp.current) rp.current.wrapper.style.transform = `scale(${scale})`; }, [scale]);

  return <div ref={root} style={{ position: 'relative', overflow: 'hidden', width, height: meta.height * scale }} />;
}
