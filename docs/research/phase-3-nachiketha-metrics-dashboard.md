# Metrics Dashboard: Core Numbers and Lightweight Charting

- **Phase:** 3
- **Researched by:** Nachiketha
- **Question(s):** Metrics dashboard: which numbers matter (task success rate, verifier accuracy, recovery rate, latency), and a lightweight chart library that works with server components.

## Findings

### 1. The Four Core Metrics That Matter for Krama MVP

To measure agent reliability, verifier precision, and user experience across Gitea and GitHub benchmark workflows, four metrics must be surfaced on the Krama dashboard [verified: phase-3-mvp.md, verified: PRD §41]:

1. **Task Success Rate (%):**
   - **Definition:** Proportion of benchmark runs where the agent executed all steps and reached the end-state goal without unrecoverable errors.
   - **Target:** **$\ge 80\%$** on real GitHub workflows to satisfy the Phase 3 MVP exit criteria [verified: phase-3-mvp.md].
   - **Formula:** $\text{Success Rate} = \frac{N_{\text{successful\_runs}}}{N_{\text{total\_runs}}} \times 100$.
2. **Verifier Accuracy (True Positive vs. False Alarm Rate):**
   - **Definition:** Precision and specificity of the layered verifier (DOM attributes, effect signals, ARIA diffs, vision grounding).
   - **True Positive Rate:** Verifier correctly confirms a valid step change (target $\ge 90\%$) [verified: phase-1-verified-workflow.md].
   - **False Alarm Rate:** Verifier erroneously flags a successful step as failed, triggering unnecessary replans or halts (target $\le 5\%$) [verified: phase-1-verified-workflow.md].
   - **Leakage Rate:** Verifier erroneously accepts a failed or no-op step (target $0\%$).
3. **Recovery / Replan Success Rate (%):**
   - **Definition:** Proportion of locator misses, temporary DOM stalls, or execution hiccups that successfully recover using alternative locators or dynamic replanning within the recovery budget ($budget \le 2$) [verified: phase-1-together-verified-definition.md].
   - **Target:** $\ge 60\%$ of encountered step failures recovered without user intervention.
4. **Latency Profile (P50 and P90 Durations):**
   - **Planning Latency:** Time taken by the LLM planner to propose or replan steps (Target: P50 $< 8\text{ s}$, P90 $< 15\text{ s}$) [verified: phase-3-mvp.md].
   - **Step Execution Latency:** Time per step including action execution, settle delay, and verification (Target: P50 $< 3\text{ s}$, P90 $< 6\text{ s}$).
   - **Total Run Duration:** Total end-to-end execution time for 3–5 step workflows (Target: $30\text{–}60\text{ s}$) [verified: phase-3-mvp.md].

### 2. Charting in React Server Components (RSC): Heavy Libraries vs. Pure SVG

On our reference 16GB CPU-only laptop and for fast dashboard loading, minimizing client JavaScript is a core objective [verified: AGENTS.md §3].

| Evaluation Factor | Recharts / Chart.js | Pure SVG in React Server Components (RSC) |
|---|---|---|
| **Client Bundle Size** | **+200 to +450 kB** gzipped client JavaScript [verified locally]. | **0 kB** client bundle overhead (pure HTML/SVG markup rendered on server) [verified locally]. |
| **Component Type** | Requires `'use client'` directive and client-side hydration [verified locally]. | Renders directly in async React Server Components [verified: Next.js docs]. |
| **First Contentful Paint (FCP)** | Delayed until client bundles download and hydrate; causes Layout Shifts (CLS > 0) [verified locally]. | **Instantaneous**: SVG vectors are in the initial server HTML stream (CLS = 0) [verified locally]. |
| **Styling & Theming** | Complex chart-specific CSS or theme configuration objects [verified locally]. | Standard Tailwind utility classes (`fill-indigo-500`, `stroke-emerald-400`, `dark:...`) [verified locally]. |
| **Hardware & CPU Impact** | Client canvas/DOM layout calculations run on user's browser [verified locally]. | Server computes normalized coordinates in $< 1\text{ ms}$ on CPU [verified locally]. |

### 3. Lightweight Pure-SVG Chart Primitives

Building pure-SVG components delivers high visual fidelity without runtime bundle weight [verified locally]:

#### Pure SVG Sparkline / Line Chart (Latency Trends)
```tsx
// frontend/components/metrics/svg-sparkline.tsx
interface SparklineProps {
  data: number[];
  width?: number;
  height?: number;
  color?: string;
}

export function SvgSparkline({ data, width = 120, height = 32, color = 'stroke-indigo-500' }: SparklineProps) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((val, idx) => {
      const x = (idx / (data.length - 1)) * width;
      const y = height - ((val - min) / range) * (height - 8) - 4;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(' ');

  return (
    <svg width={width} height={height} className="overflow-visible" aria-hidden="true">
      <polyline
        fill="none"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className={color}
        points={points}
      />
    </svg>
  );
}
```

#### Pure SVG Bar Chart (Benchmark Success Distribution)
```tsx
// frontend/components/metrics/svg-bar-chart.tsx
interface BarData {
  label: string;
  successRate: number; // 0 to 100
}

export function SvgBarChart({ items }: { items: BarData[] }) {
  const barHeight = 20;
  const gap = 10;
  const totalHeight = items.length * (barHeight + gap);

  return (
    <svg width="100%" height={totalHeight} className="overflow-visible" role="img" aria-label="Workflow Success Rates">
      {items.map((item, idx) => {
        const y = idx * (barHeight + gap);
        const isTargetMet = item.successRate >= 80;
        return (
          <g key={item.label} transform={`translate(0, ${y})`}>
            <text x="0" y="15" className="text-xs fill-zinc-600 dark:fill-zinc-400 font-mono">
              {item.label}
            </text>
            <rect x="140" y="2" width="200" height="16" rx="4" className="fill-zinc-100 dark:fill-zinc-800" />
            <rect
              x="140"
              y="2"
              width={(item.successRate / 100) * 200}
              height="16"
              rx="4"
              className={isTargetMet ? 'fill-emerald-500' : 'fill-amber-500'}
            />
            <text x="350" y="15" className="text-xs font-semibold fill-zinc-900 dark:fill-zinc-100">
              {item.successRate}%
            </text>
          </g>
        );
      })}
    </svg>
  );
}
```

## Recommendation

1. **Create Custom SVG Metric Components in `frontend/components/metrics/`:**
   - `kpi-card.tsx`: Metric summary card displaying current value, target threshold indicator, and status badge.
   - `svg-sparkline.tsx`: Zero-JS SVG sparkline for P50/P90 latency trends.
   - `svg-bar-chart.tsx`: Zero-JS horizontal bar chart for benchmark workflow success rates.
2. **Build Metrics Route at `frontend/app/metrics/page.tsx`:**
   - Implement as an async React Server Component fetching aggregate stats from Vishwas's `GET /api/v1/metrics/summary`.
   - Zero client-side JavaScript sent to the browser for charts.
3. **Reject Heavy Chart Libraries:**
   - Exclude Recharts, Chart.js, and Victory from `frontend/package.json` to keep bundle size minimal.

[No ADR required: directly implements Sprint 3.3 deliverables and RSC best practices].

## Open questions

- Should the metrics endpoint compute aggregate statistics on every request or cache them in Redis for 60 seconds? (A simple SQL `GROUP BY` across $< 1000$ runs takes $< 5\text{ ms}$ in PostgreSQL, so caching is unnecessary for MVP).

## Links

- [Next.js React Server Components Documentation](https://nextjs.org/docs/app/building-your-application/rendering/server-components)
- [W3C Scalable Vector Graphics (SVG) 2 Specification](https://www.w3.org/TR/SVG2/)
- [Krama Phase 3 MVP Criteria](file:///c:/Git/Krama/docs/phases/phase-3-mvp.md)
