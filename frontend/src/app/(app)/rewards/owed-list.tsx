"use client";

import { useRouter } from "next/navigation";
import { useId, useState, useTransition } from "react";
import { LocalTime } from "@/components/local-time";
import { formatSats, REASON_LABELS, RewardFor } from "@/components/reward-bits";
import { muted } from "@/components/ui";
import { apiRequest } from "@/lib/api-client";
import type { OwedGroup, Reward } from "@/lib/types";

export function OwedList({ initialGroups }: { initialGroups: OwedGroup[] }) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  // Kept client-side so a recorded payment disappears at once and the totals follow
  const [groups, setGroups] = useState(initialGroups);

  function recorded(paid: Reward) {
    setGroups((gs) =>
      gs
        .map((g) => ({
          ...g,
          rewards: g.rewards.filter((r) => r.id !== paid.id),
          total_owed_sats: g.rewards.some((r) => r.id === paid.id)
            ? g.total_owed_sats - paid.amount_sats
            : g.total_owed_sats,
        }))
        .filter((g) => g.rewards.length > 0),
    );
    // Refresh the server-rendered parts, e.g. the admin's own balance
    startTransition(() => router.refresh());
  }

  if (groups.length === 0) return <p className={`text-sm ${muted}`}>Nothing is owed.</p>;

  return (
    <ol className="flex flex-col gap-4">
      {groups.map((g) => (
        <li key={g.recipient_id} className="flex flex-col gap-2 rounded border border-zinc-300 p-3 dark:border-zinc-700">
          <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
            <div className="flex flex-col">
              <span className="font-medium">{g.recipient_username}</span>
              <span className={`break-all text-xs ${muted}`}>
                {g.blink_address ?? "No Lightning address on file"}
              </span>
            </div>
            <span className="font-semibold tabular-nums">{formatSats(g.total_owed_sats)} owed</span>
          </header>
          <ul className="flex flex-col divide-y divide-zinc-200 dark:divide-zinc-800">
            {g.rewards.map((r) => (
              <OwedRow key={r.id} reward={r} onRecorded={recorded} />
            ))}
          </ul>
        </li>
      ))}
    </ol>
  );
}

function OwedRow({ reward, onRecorded }: { reward: Reward; onRecorded: (r: Reward) => void }) {
  const id = useId();
  const [open, setOpen] = useState(false);
  const [ref, setRef] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    const result = await apiRequest<Reward>(`/api/rewards/${reward.id}/paid`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payment_ref: ref }),
    });
    setSaving(false);
    if (!result.ok) return setError(result.error);
    onRecorded(result.data);
  }

  return (
    <li className="flex flex-col gap-2 py-2 text-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <div className="flex flex-col gap-0.5">
          <span>
            {REASON_LABELS[reward.reason]} · <RewardFor reward={reward} />
          </span>
          {reward.note && <span className={`whitespace-pre-wrap text-xs ${muted}`}>{reward.note}</span>}
          <span className={`text-xs ${muted}`}>
            <LocalTime iso={reward.created_at} />
          </span>
        </div>
        <span className="tabular-nums">{formatSats(reward.amount_sats)}</span>
      </div>

      {open ? (
        <form onSubmit={submit} className="flex flex-col gap-2">
          <label htmlFor={`${id}-ref`} className="text-xs font-medium">
            Payment reference (from the payment you already made)
          </label>
          <input
            id={`${id}-ref`}
            value={ref}
            onChange={(e) => setRef(e.target.value)}
            required
            maxLength={200}
            autoFocus
            className="w-full rounded border border-zinc-400 bg-transparent px-3 py-2 text-base sm:text-sm dark:border-zinc-600"
          />
          <div className="flex items-center gap-4">
            <button
              type="submit"
              disabled={saving || !ref.trim()}
              className="min-h-11 rounded bg-foreground px-4 text-sm text-background disabled:opacity-50"
            >
              {saving ? "Recording…" : "Record as paid"}
            </button>
            <button type="button" onClick={() => setOpen(false)} className="min-h-9 text-sm underline">
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <div>
          <button onClick={() => setOpen(true)} className="min-h-9 rounded border border-zinc-400 px-3 text-sm">
            Mark paid
          </button>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </li>
  );
}
