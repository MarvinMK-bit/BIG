import Link from "next/link";
import { questionLabel } from "@/lib/script";
import type { Reward, RewardReason, RewardStatus } from "@/lib/types";

export const REASON_LABELS: Record<RewardReason, string> = {
  feedback: "Feedback",
  mark_scheme: "Mark scheme",
  scheme_improvement: "Scheme improvement",
};

const STATUS_STYLES: Record<RewardStatus, string> = {
  owed: "bg-amber-200 text-amber-900 dark:bg-amber-900 dark:text-amber-100",
  paid: "bg-green-200 text-green-900 dark:bg-green-900 dark:text-green-100",
  cancelled: "bg-zinc-200 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-100",
};

// "paid" is a record an admin made; the tooltip says so rather than implying BIG sent anything.
export function RewardStatusBadge({ reward }: { reward: Reward }) {
  const title =
    reward.status === "paid"
      ? `Recorded as paid by an admin${reward.payment_ref ? ` (ref ${reward.payment_ref})` : ""}`
      : undefined;
  return (
    <span
      title={title}
      className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_STYLES[reward.status]}`}
    >
      {reward.status === "paid" ? "recorded paid" : reward.status}
    </span>
  );
}

export function formatSats(n: number): string {
  return `${n.toLocaleString("en-GB")} sats`;
}

// What the reward was for, linked where the viewer can follow it.
export function RewardFor({ reward }: { reward: Reward }) {
  const f = reward.feedback;
  if (f) {
    if (f.mark_scheme_version !== null) {
      return (
        <Link href={`/schemes/${encodeURIComponent(f.mark_scheme_version)}`} className="underline">
          <span className="font-mono">{f.public_ref}</span> on {f.mark_scheme_version}
        </Link>
      );
    }
    const q = f.question_number !== null ? `Q${questionLabel(f.question_number, f.sub_part)}` : "a question";
    return f.session_id ? (
      <Link href={`/sessions/${f.session_id}#feedback-${f.question_result_id}`} className="underline">
        <span className="font-mono">{f.public_ref}</span> on {q}
      </Link>
    ) : (
      <span>
        <span className="font-mono">{f.public_ref}</span> on {q}
      </span>
    );
  }
  if (reward.mark_scheme_version) {
    return (
      <Link href={`/schemes/${encodeURIComponent(reward.mark_scheme_version)}`} className="break-all underline">
        {reward.mark_scheme_version}
      </Link>
    );
  }
  return <span>—</span>;
}
