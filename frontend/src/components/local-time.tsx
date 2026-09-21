"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

// Server renders a deterministic UTC string; the browser swaps in its own locale/timezone
// after hydration (useSyncExternalStore avoids a hydration mismatch).
export function LocalTime({ iso }: { iso: string }) {
  const text = useSyncExternalStore(
    subscribe,
    () => new Date(iso).toLocaleString(),
    () => `${new Date(iso).toISOString().slice(0, 16).replace("T", " ")} UTC`,
  );
  return <time dateTime={iso}>{text}</time>;
}
