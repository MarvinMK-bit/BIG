"use client";

import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { muted } from "@/components/ui";
import { compareGraders, graderKey, graderLabel } from "@/lib/grader";
import type { AccuracyPoint, Bucket } from "@/lib/types";

const MAX_SERIES = 8; // one per categorical colour slot; colours are never reused
const HEIGHT = 240;
const MARGIN = { top: 12, bottom: 28, left: 40 };
const END_LABEL_WIDTH = 104;
const MIN_WIDTH_FOR_END_LABELS = 480;
const MAX_POINTS_FOR_MARKERS = 40;
const Y_TICKS = [0, 0.25, 0.5, 0.75, 1];

type Series = { key: string; label: string; color: string; points: AccuracyPoint[] };

function formatPeriod(iso: string, bucket: Bucket): string {
  // Fixed locale and UTC so server and browser render the same text
  const date = new Date(`${iso}T00:00:00Z`);
  const opts: Intl.DateTimeFormatOptions =
    bucket === "month"
      ? { month: "short", year: "numeric", timeZone: "UTC" }
      : { day: "numeric", month: "short", timeZone: "UTC" };
  const text = date.toLocaleDateString("en-GB", opts);
  return bucket === "week" ? `w/c ${text}` : text;
}

// Fits the end-label gutter: "LLM", or the scheme's name without its version
function shortLabel(p: AccuracyPoint): string {
  if (p.grader_type === "llm") return "LLM";
  const name = (p.mark_scheme_version ?? "Scheme").split("@")[0];
  return name.length > 10 ? `${name.slice(0, 9)}…` : name;
}

function percent(value: number | null): string {
  return value === null ? "—" : `${Math.round(value * 1000) / 10}%`;
}

// A series' running total as of a period: its latest point on or before it.
function asOf(series: Series, period: string): AccuracyPoint | null {
  let found: AccuracyPoint | null = null;
  for (const p of series.points) {
    if (p.period_start > period) break;
    found = p;
  }
  return found;
}

export function AccuracyChart({
  points,
  bucket,
  minJudged,
}: {
  points: AccuracyPoint[];
  bucket: Bucket;
  minJudged: number;
}) {
  const wrapper = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(640);
  const [hovered, setHovered] = useState<number | null>(null);

  useEffect(() => {
    const el = wrapper.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(240, entry.contentRect.width)));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const byKey = new Map<string, AccuracyPoint[]>();
  for (const p of [...points].sort(compareGraders)) {
    const key = graderKey(p);
    byKey.set(key, [...(byKey.get(key) ?? []), p]);
  }
  const allSeries: Series[] = [...byKey.entries()].map(([key, pts], i) => ({
    key,
    label: graderLabel(pts[0]),
    color: `var(--series-${i + 1})`,
    points: pts.sort((a, b) => a.period_start.localeCompare(b.period_start)),
  }));
  const series = allSeries.slice(0, MAX_SERIES);
  const hiddenCount = allSeries.length - series.length;

  if (series.length === 0) {
    return <p className={`text-sm ${muted}`}>No judged questions to chart yet.</p>;
  }

  const periods = [...new Set(series.flatMap((s) => s.points.map((p) => p.period_start)))].sort();
  const endLabels = width >= MIN_WIDTH_FOR_END_LABELS && series.length <= 4;
  const right = endLabels ? END_LABEL_WIDTH : 16;
  const plotWidth = width - MARGIN.left - right;
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;

  const times = periods.map((p) => Date.parse(`${p}T00:00:00Z`));
  const [t0, t1] = [times[0], times[times.length - 1]];
  const x = (period: string) =>
    t1 === t0
      ? MARGIN.left + plotWidth / 2
      : MARGIN.left + ((Date.parse(`${period}T00:00:00Z`) - t0) / (t1 - t0)) * plotWidth;
  const y = (value: number) => MARGIN.top + (1 - value) * plotHeight;

  const maxTicks = Math.max(1, Math.floor(plotWidth / 84));
  const step = Math.ceil(periods.length / maxTicks);
  const xTicks = periods.filter((_, i) => i % step === 0);

  const showMarkers = periods.length <= MAX_POINTS_FOR_MARKERS;
  const underSampled = series
    .map((s) => ({ s, last: s.points[s.points.length - 1] }))
    .filter(({ last }) => last.cumulative_judged < minJudged);

  // End labels sit at each line's last value, nudged apart so they never overlap
  const labels = series
    .map((s) => {
      const last = s.points[s.points.length - 1];
      return { s, last, y: y(last.cumulative_accuracy ?? 0) };
    })
    .sort((a, b) => a.y - b.y);
  for (let i = 1; i < labels.length; i++) {
    labels[i].y = Math.max(labels[i].y, labels[i - 1].y + 14);
  }

  function pick(clientX: number, rect: DOMRect) {
    const px = ((clientX - rect.left) / rect.width) * width;
    let best = 0;
    periods.forEach((p, i) => {
      if (Math.abs(x(p) - px) < Math.abs(x(periods[best]) - px)) best = i;
    });
    setHovered(best);
  }

  function onPointerMove(e: PointerEvent<SVGSVGElement>) {
    pick(e.clientX, e.currentTarget.getBoundingClientRect());
  }

  function onKeyDown(e: KeyboardEvent<SVGSVGElement>) {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const delta = e.key === "ArrowRight" ? 1 : -1;
      setHovered((h) => Math.min(periods.length - 1, Math.max(0, (h ?? (delta > 0 ? -1 : periods.length)) + delta)));
    } else if (e.key === "Escape") {
      setHovered(null);
    }
  }

  const hoveredPeriod = hovered === null ? null : periods[hovered];
  const tooltipLeft = hoveredPeriod === null ? 0 : (x(hoveredPeriod) / width) * 100;

  return (
    <div className="viz-root flex flex-col gap-3">
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm" aria-label="Legend">
        {series.map((s) => (
          <li key={s.key} className="flex items-center gap-2 break-all">
            <svg width="16" height="8" aria-hidden className="shrink-0">
              <line x1="0" y1="4" x2="16" y2="4" stroke={s.color} strokeWidth="2" strokeLinecap="round" />
            </svg>
            {s.label}
          </li>
        ))}
        {showMarkers && underSampled.length > 0 && (
          <li className={`flex items-center gap-2 ${muted}`}>
            <svg width="12" height="12" aria-hidden className="shrink-0">
              <circle cx="6" cy="6" r="4" fill="var(--viz-surface)" stroke="currentColor" strokeWidth="2" />
            </svg>
            Hollow: fewer than {minJudged} judged so far
          </li>
        )}
      </ul>

      {underSampled.length > 0 && (
        <p className="text-sm text-amber-800 dark:text-amber-300">
          {underSampled
            .map(({ s, last }) => `${s.label}: ${last.cumulative_judged} judged`)
            .join("; ")}{" "}
          — too few to draw conclusions (under {minJudged}).
        </p>
      )}

      <div ref={wrapper} className="relative w-full">
        <svg
          viewBox={`0 0 ${width} ${HEIGHT}`}
          width="100%"
          role="img"
          aria-label={`Cumulative accuracy per grader by ${bucket}. Use the left and right arrow keys to read values.`}
          tabIndex={0}
          className="block touch-pan-y outline-none focus-visible:ring-2 focus-visible:ring-zinc-400"
          onPointerMove={onPointerMove}
          onPointerDown={onPointerMove}
          onPointerLeave={() => setHovered(null)}
          onKeyDown={onKeyDown}
          onBlur={() => setHovered(null)}
        >
          {Y_TICKS.map((t) => (
            <g key={t}>
              <line
                x1={MARGIN.left}
                x2={MARGIN.left + plotWidth}
                y1={y(t)}
                y2={y(t)}
                stroke={t === 0 ? "var(--viz-axis)" : "var(--viz-grid)"}
                strokeWidth="1"
              />
              <text
                x={MARGIN.left - 6}
                y={y(t)}
                textAnchor="end"
                dominantBaseline="middle"
                fontSize="11"
                fill="var(--viz-text-secondary)"
              >
                {t * 100}%
              </text>
            </g>
          ))}
          {xTicks.map((p) => (
            <text
              key={p}
              x={x(p)}
              y={HEIGHT - 8}
              textAnchor="middle"
              fontSize="11"
              fill="var(--viz-text-secondary)"
            >
              {formatPeriod(p, bucket)}
            </text>
          ))}

          {hoveredPeriod !== null && (
            <line
              x1={x(hoveredPeriod)}
              x2={x(hoveredPeriod)}
              y1={MARGIN.top}
              y2={MARGIN.top + plotHeight}
              stroke="var(--viz-axis)"
              strokeWidth="1"
            />
          )}

          {series.map((s) => (
            <g key={s.key}>
              <polyline
                points={s.points.map((p) => `${x(p.period_start)},${y(p.cumulative_accuracy ?? 0)}`).join(" ")}
                fill="none"
                stroke={s.color}
                strokeWidth="2"
                strokeLinejoin="round"
                strokeLinecap="round"
              />
              {(showMarkers ? s.points : s.points.slice(-1)).map((p) => {
                const thin = p.cumulative_judged < minJudged;
                return (
                  <circle
                    key={p.period_start}
                    cx={x(p.period_start)}
                    cy={y(p.cumulative_accuracy ?? 0)}
                    r={p.period_start === hoveredPeriod ? 5 : 4}
                    fill={thin ? "var(--viz-surface)" : s.color}
                    stroke={thin ? s.color : "var(--viz-surface)"}
                    strokeWidth="2"
                  />
                );
              })}
            </g>
          ))}

          {endLabels &&
            labels.map(({ s, last, y: labelY }) => (
              <text
                key={s.key}
                x={MARGIN.left + plotWidth + 10}
                y={labelY}
                dominantBaseline="middle"
                fontSize="11"
                fill="var(--viz-text-secondary)"
              >
                {shortLabel(s.points[0])} {percent(last.cumulative_accuracy)}
              </text>
            ))}
        </svg>

        {hoveredPeriod !== null && (
          <div
            role="status"
            className="pointer-events-none absolute top-0 z-10 w-56 max-w-[70%] rounded border border-zinc-300 bg-white p-2 text-xs shadow-sm dark:border-zinc-700 dark:bg-zinc-900"
            style={
              tooltipLeft > 50
                ? { right: `${100 - tooltipLeft}%`, marginRight: 8 }
                : { left: `${tooltipLeft}%`, marginLeft: 8 }
            }
          >
            <p className={`mb-1 ${muted}`}>{formatPeriod(hoveredPeriod, bucket)}</p>
            <ul className="flex flex-col gap-1">
              {series.map((s) => {
                const p = asOf(s, hoveredPeriod);
                if (!p) return null;
                const carried = p.period_start !== hoveredPeriod;
                return (
                  <li key={s.key} className="flex items-start gap-2">
                    <svg width="12" height="8" aria-hidden className="mt-1 shrink-0">
                      <line x1="0" y1="4" x2="12" y2="4" stroke={s.color} strokeWidth="2" strokeLinecap="round" />
                    </svg>
                    <span className="min-w-0">
                      <span className="font-semibold">{percent(p.cumulative_accuracy)}</span>{" "}
                      <span className={muted}>
                        ({p.cumulative_correct}/{p.cumulative_judged}
                        {carried ? ", no new verdicts" : ""})
                      </span>
                      <span className={`block break-all ${muted}`}>{s.label}</span>
                    </span>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </div>

      {hiddenCount > 0 && (
        <p className={`text-sm ${muted}`}>
          {hiddenCount} more grader{hiddenCount === 1 ? "" : "s"} not charted; see the table and
          summary cards.
        </p>
      )}

      <details className="text-sm">
        <summary className="cursor-pointer underline">Show as table</summary>
        <div className="mt-2 overflow-x-auto">
          <table className="w-full text-left">
            <thead>
              <tr className={muted}>
                <th className="py-1 pr-3 font-normal">Period</th>
                <th className="py-1 pr-3 font-normal">Grader</th>
                <th className="py-1 pr-3 font-normal">This period</th>
                <th className="py-1 font-normal">Cumulative</th>
              </tr>
            </thead>
            <tbody>
              {allSeries.flatMap((s) =>
                s.points.map((p) => (
                  <tr key={`${s.key}|${p.period_start}`} className="border-t border-zinc-200 dark:border-zinc-800">
                    <td className="py-1 pr-3 whitespace-nowrap">{formatPeriod(p.period_start, bucket)}</td>
                    <td className="py-1 pr-3 break-all">{s.label}</td>
                    <td className="py-1 pr-3 whitespace-nowrap">
                      {percent(p.accuracy)} ({p.correct_decisions}/{p.judged_questions})
                    </td>
                    <td className="py-1 whitespace-nowrap">
                      {percent(p.cumulative_accuracy)} ({p.cumulative_correct}/{p.cumulative_judged})
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </details>
    </div>
  );
}
