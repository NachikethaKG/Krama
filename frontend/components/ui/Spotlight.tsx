"use client";

import { type HTMLAttributes, type MouseEvent, useRef } from "react";

/** A container whose background lights up under the mouse, in its `--kr-tone` colour. */
export function Spotlight({ className = "", children, onMouseMove, ...rest }: HTMLAttributes<HTMLDivElement>) {
  const ref = useRef<HTMLDivElement>(null);
  const move = (event: MouseEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (el) {
      const rect = el.getBoundingClientRect();
      el.style.setProperty("--mx", `${event.clientX - rect.left}px`);
      el.style.setProperty("--my", `${event.clientY - rect.top}px`);
    }
    onMouseMove?.(event);
  };
  return (
    <div ref={ref} onMouseMove={move} className={`kr-spotlight ${className}`} {...rest}>
      {children}
    </div>
  );
}
