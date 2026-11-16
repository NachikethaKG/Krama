"use client";

import { type HTMLAttributes, type MouseEvent, useRef } from "react";

/** A card that tilts in 3D towards the mouse and lights up where the pointer is. */
export function TiltCard({
  className = "",
  children,
  max = 8,
  ...rest
}: HTMLAttributes<HTMLDivElement> & { max?: number }) {
  const ref = useRef<HTMLDivElement>(null);

  const move = (event: MouseEvent<HTMLDivElement>) => {
    const el = ref.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const x = (event.clientX - rect.left) / rect.width;
    const y = (event.clientY - rect.top) / rect.height;
    el.style.transform = `perspective(900px) rotateX(${(0.5 - y) * max}deg) rotateY(${(x - 0.5) * max}deg)`;
    el.style.setProperty("--mx", `${x * 100}%`);
    el.style.setProperty("--my", `${y * 100}%`);
  };
  const leave = () => {
    if (ref.current) ref.current.style.transform = "";
  };

  return (
    <div ref={ref} onMouseMove={move} onMouseLeave={leave} className={`kr-tilt kr-spotlight ${className}`} {...rest}>
      {children}
    </div>
  );
}
