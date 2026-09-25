import { LocalTime } from "@/components/local-time";
import { formatSats, REASON_LABELS, RewardFor, RewardStatusBadge } from "@/components/reward-bits";
import { muted } from "@/components/ui";
import { backendGet } from "@/lib/backend";
import type { Me, MyRewards, OwedGroup } from "@/lib/types";
import { OwedList } from "./owed-list";

export default async function RewardsPage() {
  const me = await backendGet<Me>("/auth/me");
  const [mine, owed] = await Promise.all([
    backendGet<MyRewards>("/rewards/me"),
    me.is_admin ? backendGet<OwedGroup[]>("/rewards/owed") : Promise.resolve(null),
  ]);

  return (
    <main className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <h1 className="text-xl font-semibold">Rewards</h1>
        <p className="rounded border border-zinc-300 p-3 text-sm dark:border-zinc-700">
          Payouts are recorded by hand for now. Lightning payment is not yet wired up, so nothing on
          this page sends or receives sats. &ldquo;Recorded paid&rdquo; means an admin has noted a
          payment they made outside BIG.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <div>
          <p className={`text-sm ${muted}`}>Owed to you</p>
          <p className="text-2xl font-semibold">{formatSats(mine.total_owed_sats)}</p>
        </div>

        {mine.rewards.length === 0 ? (
          <p className={`text-sm ${muted}`}>
            No rewards yet. Approved feedback and accepted mark schemes earn sats.
          </p>
        ) : (
          <div className="-mx-4 overflow-x-auto px-4">
            <table className="w-full min-w-[32rem] text-left text-sm">
              <thead className={`border-b border-zinc-300 text-xs dark:border-zinc-700 ${muted}`}>
                <tr>
                  <th className="py-2 pr-3 font-medium">Date</th>
                  <th className="py-2 pr-3 font-medium">For</th>
                  <th className="py-2 pr-3 font-medium">Reason</th>
                  <th className="py-2 pr-3 text-right font-medium">Amount</th>
                  <th className="py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {mine.rewards.map((r) => (
                  <tr key={r.id} className="border-b border-zinc-200 align-top dark:border-zinc-800">
                    <td className="py-2 pr-3 whitespace-nowrap">
                      <LocalTime iso={r.created_at} />
                    </td>
                    <td className="py-2 pr-3">
                      <RewardFor reward={r} />
                      {r.note && <p className={`text-xs whitespace-pre-wrap ${muted}`}>{r.note}</p>}
                    </td>
                    <td className="py-2 pr-3">{REASON_LABELS[r.reason]}</td>
                    <td className="py-2 pr-3 text-right whitespace-nowrap tabular-nums">{formatSats(r.amount_sats)}</td>
                    <td className="py-2">
                      <RewardStatusBadge reward={r} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {owed && (
        <section className="flex flex-col gap-3 border-t border-zinc-300 pt-6 dark:border-zinc-700">
          <h2 className="text-lg font-semibold">Owed by recipient</h2>
          <p className={`text-sm ${muted}`}>
            Pay each person outside BIG first, then record it here with the payment&apos;s reference.
          </p>
          <OwedList initialGroups={owed} />
        </section>
      )}
    </main>
  );
}
