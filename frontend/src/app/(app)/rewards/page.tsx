import { LocalTime } from "@/components/local-time";
import { formatSats, REASON_LABELS, RewardFor, RewardStatusBadge } from "@/components/reward-bits";
import { muted } from "@/components/ui";
import { backendGet } from "@/lib/backend";
import type { Me, MyRewards, OwedGroup, PayoutStatus } from "@/lib/types";
import { AddressForm } from "./address-form";
import { OwedList } from "./owed-list";
import { PayoutsBanner } from "./payouts-banner";

export default async function RewardsPage() {
  const me = await backendGet<Me>("/auth/me");
  const [mine, owed, payouts] = await Promise.all([
    backendGet<MyRewards>("/rewards/me"),
    me.is_admin ? backendGet<OwedGroup[]>("/rewards/owed") : Promise.resolve(null),
    me.is_admin ? backendGet<PayoutStatus>("/rewards/payouts") : Promise.resolve(null),
  ]);

  return (
    <main className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <h1 className="text-xl font-semibold">Rewards</h1>
        <p className="rounded border border-zinc-300 p-3 text-sm dark:border-zinc-700">
          Rewards are paid over Lightning to the address below, one at a time, by an admin. A reward
          marked &ldquo;owed&rdquo; has not been sent. &ldquo;Recorded paid&rdquo; means an admin
          paid it outside BIG and noted it here.
        </p>
      </header>

      <AddressForm initial={me.blink_address} />

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

      {owed && payouts && (
        <section className="flex flex-col gap-3 border-t border-zinc-300 pt-6 dark:border-zinc-700">
          <h2 className="text-lg font-semibold">Owed by recipient</h2>
          <PayoutsBanner status={payouts} />
          <p className={`text-sm ${muted}`}>
            Pay sends one reward to the recipient&apos;s Lightning address. If you paid someone
            another way, use &ldquo;Record payment&rdquo; with that payment&apos;s reference instead.
          </p>
          <OwedList initialGroups={owed} payouts={payouts} />
        </section>
      )}
    </main>
  );
}
