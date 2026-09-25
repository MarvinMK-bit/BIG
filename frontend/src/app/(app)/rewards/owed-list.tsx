"use client";

import { useRouter } from "next/navigation";
import { useId, useState, useTransition } from "react";
import { LocalTime } from "@/components/local-time";
import { formatSats, REASON_LABELS, RewardFor } from "@/components/reward-bits";
import { muted } from "@/components/ui";
import { apiRequest, postJson } from "@/lib/api-client";
import {
  BLOCKING_ATTEMPTS,
  type AttemptStatus,
  type OwedGroup,
  type OwedReward,
  type PayoutAttempt,
  type PayoutResult,
  type PayoutStatus,
  type Reward,
} from "@/lib/types";

const ATTEMPT_STYLES: Record<AttemptStatus, string> = {
  attempting: "text-amber-800 dark:text-amber-300",
  pending: "text-amber-800 dark:text-amber-300",
  success: "text-green-800 dark:text-green-300",
  already_paid: "text-green-800 dark:text-green-300",
  failed: "text-red-700 dark:text-red-400",
};

const ATTEMPT_LABELS: Record<AttemptStatus, string> = {
  attempting: "started, never finished",
  pending: "pending — may still arrive",
  success: "sent",
  already_paid: "already paid",
  failed: "failed",
};

export function OwedList({ initialGroups, payouts }: { initialGroups: OwedGroup[]; payouts: PayoutStatus }) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  // Kept client-side so a paid reward leaves at once and the totals follow
  const [groups, setGroups] = useState(initialGroups);
  const [notice, setNotice] = useState<string | null>(null);

  function removePaid(paid: Reward) {
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

  function addAttempt(attempt: PayoutAttempt) {
    setGroups((gs) =>
      gs.map((g) => ({
        ...g,
        rewards: g.rewards.map((r) =>
          r.id === attempt.reward_id ? { ...r, attempts: [...r.attempts, attempt] } : r,
        ),
      })),
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {notice && (
        <p role="status" className="rounded border border-green-700 p-3 text-sm text-green-900 dark:border-green-500 dark:text-green-200">
          {notice}
        </p>
      )}
      {groups.length === 0 ? (
        <p className={`text-sm ${muted}`}>Nothing is owed.</p>
      ) : (
        <ol className="flex flex-col gap-4">
          {groups.map((g) => (
            <li key={g.recipient_id} className="flex flex-col gap-2 rounded border border-zinc-300 p-3 dark:border-zinc-700">
              <header className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <div className="flex flex-col">
                  <span className="font-medium">{g.recipient_username}</span>
                  <span className={`break-all text-xs ${g.blink_address ? muted : "text-red-700 dark:text-red-400"}`}>
                    {g.blink_address ?? "No Lightning address saved — can't be paid"}
                  </span>
                </div>
                <span className="font-semibold tabular-nums">{formatSats(g.total_owed_sats)} owed</span>
              </header>
              <ul className="flex flex-col divide-y divide-zinc-200 dark:divide-zinc-800">
                {g.rewards.map((r) => (
                  <OwedRow
                    key={r.id}
                    reward={r}
                    address={g.blink_address}
                    payouts={payouts}
                    onPaid={(paid, how) => {
                      setNotice(how);
                      removePaid(paid);
                    }}
                    onAttempt={addAttempt}
                  />
                ))}
              </ul>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

function OwedRow({
  reward,
  address,
  payouts,
  onPaid,
  onAttempt,
}: {
  reward: OwedReward;
  address: string | null;
  payouts: PayoutStatus;
  onPaid: (reward: Reward, notice: string) => void;
  onAttempt: (attempt: PayoutAttempt) => void;
}) {
  const [recording, setRecording] = useState(false);
  const [paying, setPaying] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const blocking = reward.attempts.find((a) => BLOCKING_ATTEMPTS.has(a.status));
  const payBlockedBy = !address
    ? "The recipient has no Lightning address"
    : payouts.problem
      ? payouts.problem
      : blocking
        ? "An earlier attempt may have paid this; check Blink before doing anything else"
        : null;

  async function pay() {
    if (!address) return;
    const where =
      payouts.network === "mainnet"
        ? "MAINNET: this sends REAL BITCOIN and cannot be undone."
        : payouts.network === "staging"
          ? "Staging: test sats only, no real money."
          : `Unrecognised API (${payouts.api_host}).`;
    if (!confirm(`Send ${formatSats(reward.amount_sats)} to ${address}?\n\n${where}`)) return;

    setError(null);
    setPaying(true);
    const result = await postJson<PayoutResult>(`/api/rewards/${reward.id}/pay`);
    setPaying(false);
    if (!result.ok) return setError(result.error);

    const { attempt, reward: updated } = result.data;
    if (updated.status === "paid") {
      const net = payouts.network === "staging" ? " (staging test sats)" : "";
      onPaid(
        updated,
        attempt.status === "already_paid"
          ? `Blink reports ${formatSats(attempt.amount_sats)} to ${attempt.lightning_address} was already paid${net}.`
          : `Blink reports ${formatSats(attempt.amount_sats)} sent to ${attempt.lightning_address}${net}.`,
      );
      return;
    }
    onAttempt(attempt);
    setError(
      attempt.status === "pending"
        ? `Payment pending: it may still arrive. ${attempt.error_message ?? ""}`.trim()
        : `Payment failed; nothing was sent, and you can try again. ${attempt.error_message ?? ""}`.trim(),
    );
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

      {reward.attempts.length > 0 && (
        <ol aria-label="Payment attempts" className="flex flex-col gap-1 border-l-2 border-zinc-300 pl-3 text-xs dark:border-zinc-700">
          {reward.attempts.map((a) => (
            <li key={a.id} className="flex flex-col">
              <span>
                <LocalTime iso={a.created_at} /> ·{" "}
                <span className={`font-medium ${ATTEMPT_STYLES[a.status]}`}>{ATTEMPT_LABELS[a.status]}</span> ·{" "}
                {formatSats(a.amount_sats)} to <span className="break-all">{a.lightning_address}</span>
              </span>
              {a.error_message && <span className={`break-words ${muted}`}>{a.error_message}</span>}
            </li>
          ))}
        </ol>
      )}

      {recording ? (
        <RecordPaymentForm
          reward={reward}
          onDone={(paid) => onPaid(paid, `Recorded ${formatSats(paid.amount_sats)} to ${paid.recipient_username} as paid outside BIG.`)}
          onCancel={() => setRecording(false)}
        />
      ) : (
        <div className="flex flex-wrap gap-2">
          <button
            onClick={pay}
            disabled={paying || payBlockedBy !== null}
            title={payBlockedBy ?? undefined}
            className="min-h-11 rounded bg-foreground px-4 text-sm text-background disabled:opacity-40"
          >
            {paying ? "Paying…" : `Pay ${formatSats(reward.amount_sats)}`}
          </button>
          <button onClick={() => setRecording(true)} disabled={paying} className="min-h-11 rounded border border-zinc-400 px-3 text-sm">
            Record payment
          </button>
        </div>
      )}
      {payBlockedBy && !recording && <p className={`text-xs ${muted}`}>{payBlockedBy}.</p>}
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </li>
  );
}

// For a payment made outside BIG: records it against the reward without sending anything.
function RecordPaymentForm({
  reward,
  onDone,
  onCancel,
}: {
  reward: Reward;
  onDone: (paid: Reward) => void;
  onCancel: () => void;
}) {
  const id = useId();
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
    onDone(result.data);
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <label htmlFor={`${id}-ref`} className="text-xs font-medium">
        Reference of the payment you already made outside BIG
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
        <button type="button" onClick={onCancel} className="min-h-9 text-sm underline">
          Cancel
        </button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </form>
  );
}
