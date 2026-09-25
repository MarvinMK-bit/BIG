"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

const UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 24 * 3600],
  ["month", 30 * 24 * 3600],
  ["week", 7 * 24 * 3600],
  ["day", 24 * 3600],
  ["hour", 3600],
  ["minute", 60],
];

function relative(iso: string): string {
  const seconds = (Date.parse(iso) - Date.now()) / 1000;
  const format = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  for (const [unit, size] of UNITS) {
    if (Math.abs(seconds) >= size) return format.format(Math.round(seconds / size), unit);
  }
  return "just now";
}

// "3 hours ago". Like LocalTime, the server renders a fixed UTC date and the browser swaps in
// the relative text after hydration; the full local time is in the tooltip.
export function RelativeTime({ iso }: { iso: string }) {
  const text = useSyncExternalStore(subscribe, () => relative(iso), () => iso.slice(0, 10));
  const full = useSyncExternalStore(
    subscribe,
    () => new Date(iso).toLocaleString(),
    () => `${new Date(iso).toISOString().slice(0, 16).replace("T", " ")} UTC`,
  );
  return (
    <time dateTime={iso} title={full}>
      {text}
    </time>
  );
}
