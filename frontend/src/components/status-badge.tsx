import type { SessionStatus } from "@/lib/types";

const STYLES: Record<SessionStatus, string> = {
  pending: "bg-zinc-200 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-100",
  processing: "bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-100",
  completed: "bg-green-200 text-green-900 dark:bg-green-900 dark:text-green-100",
  failed: "bg-red-200 text-red-900 dark:bg-red-900 dark:text-red-100",
};

export function StatusBadge({ status }: { status: SessionStatus }) {
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STYLES[status]}`}>
      {status}
    </span>
  );
}
