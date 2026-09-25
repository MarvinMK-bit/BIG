"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { RelativeTime } from "@/components/relative-time";
import { muted } from "@/components/ui";
import { apiRequest } from "@/lib/api-client";
import { questionLabel } from "@/lib/script";
import { formatSats } from "@/components/reward-bits";
import type { Feedback, FeedbackReview, FeedbackStatus, Reward } from "@/lib/types";

type Decision = Exclude<FeedbackStatus, "pending">;

const ACTIONS: { status: Decision; label: string; className: string }[] = [
  { status: "approved", label: "Approve", className: "border-green-700 text-green-800 dark:border-green-500 dark:text-green-300" },
  { status: "rejected", label: "Reject", className: "border-red-600 text-red-700 dark:text-red-400" },
  { status: "muted", label: "Mute", className: "border-zinc-400" },
];

function TargetLink({ item }: { item: Feedback }) {
  if (item.mark_scheme_version !== null) {
    return (
      <Link href={`/schemes/${encodeURIComponent(item.mark_scheme_version)}`} className="break-all underline">
        Scheme {item.mark_scheme_version}
      </Link>
    );
  }
  const label = item.question_number !== null ? `Q${questionLabel(item.question_number, item.sub_part)}` : "Question";
  return (
    <Link href={`/sessions/${item.session_id}#feedback-${item.question_result_id}`} className="underline">
      {label} of a graded script
    </Link>
  );
}

export function ModerationList({ initialItems }: { initialItems: Feedback[] }) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  // Kept client-side, so decided items stay on screen (with the payout reminder) after the
  // refresh that updates the nav badge
  const [decided, setDecided] = useState<Record<string, { status: Decision; reward: Reward | null }>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function decide(item: Feedback, status: Decision) {
    setBusy(item.id);
    setErrors((e) => ({ ...e, [item.id]: "" }));
    const result = await apiRequest<FeedbackReview>(`/api/feedback/${item.id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status }),
    });
    setBusy(null);
    if (!result.ok) return setErrors((e) => ({ ...e, [item.id]: result.error }));
    setDecided((d) => ({ ...d, [item.id]: { status, reward: result.data.reward } }));
    startTransition(() => router.refresh());
  }

  if (initialItems.length === 0) {
    return <p className={`text-sm ${muted}`}>Nothing to review.</p>;
  }

  return (
    <ol className="flex flex-col gap-3">
      {initialItems.map((item) => {
        const decision = decided[item.id]?.status;
        const reward = decided[item.id]?.reward ?? null;
        return (
          <li
            key={item.id}
            className={`flex flex-col gap-2 rounded border border-zinc-300 p-3 dark:border-zinc-700 ${
              decision && decision !== "approved" ? "opacity-60" : ""
            }`}
          >
            <header className="flex flex-wrap items-baseline gap-x-2 gap-y-1 text-sm">
              <span className={`font-mono text-xs ${muted}`}>{item.public_ref}</span>
              <span className="font-medium">{item.author_username}</span>
              {item.author_context && <span className={muted}>{item.author_context}</span>}
              <span className={`text-xs ${muted}`}>
                <RelativeTime iso={item.created_at} />
                {item.edited_at && " · edited"}
              </span>
            </header>
            <p className="text-sm">
              <TargetLink item={item} />
              {item.parent_public_ref && <span className={muted}> · reply to {item.parent_public_ref}</span>}
            </p>
            <p className="whitespace-pre-wrap break-words text-sm">{item.body}</p>

            {decision === "approved" ? (
              <div role="status" className="flex flex-col gap-0.5 text-sm">
                <p className="font-medium text-green-800 dark:text-green-300">
                  {reward
                    ? `Approved — ${formatSats(reward.amount_sats)} payable to ${reward.recipient_username}`
                    : "Approved — no reward was recorded"}
                </p>
                {reward && (
                  <p className={`text-xs ${muted}`}>
                    Recorded in the ledger as {reward.status}. Payouts are not yet automated; nothing
                    has been paid. Pay by hand, then mark it paid on{" "}
                    <Link href="/rewards" className="underline">
                      Rewards
                    </Link>
                    .
                  </p>
                )}
              </div>
            ) : decision ? (
              <p role="status" className="text-sm font-medium">
                {decision === "rejected" ? "Rejected" : "Muted"}
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {ACTIONS.map((action) => (
                  <button
                    key={action.status}
                    onClick={() => decide(item, action.status)}
                    disabled={busy !== null}
                    className={`min-h-11 flex-1 rounded border px-4 text-sm disabled:opacity-50 sm:flex-none ${action.className}`}
                  >
                    {busy === item.id ? "…" : action.label}
                  </button>
                ))}
              </div>
            )}

            {errors[item.id] && (
              <p role="alert" className="text-sm text-red-600">
                {errors[item.id]}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
