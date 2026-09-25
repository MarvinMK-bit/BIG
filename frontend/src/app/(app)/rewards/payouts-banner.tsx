import type { PayoutStatus } from "@/lib/types";

// Readable at a glance: two labelled facts (on/off, which network) plus one sentence, coloured by
// the risk of pressing Pay: red for real money, amber for test sats, grey for off.
export function PayoutsBanner({ status }: { status: PayoutStatus }) {
  const live = status.enabled && status.problem === null;
  const network =
    status.network === "mainnet" ? "MAINNET" : status.network === "staging" ? "STAGING" : status.api_host;

  let tone: string;
  let message: string;
  if (live && status.network === "mainnet") {
    tone = "border-red-700 bg-red-100 text-red-950 dark:border-red-500 dark:bg-red-950 dark:text-red-50";
    message = "Pay sends REAL BITCOIN from BIG's Blink wallet. Every payment is final.";
  } else if (live && status.network === "staging") {
    tone = "border-amber-600 bg-amber-100 text-amber-950 dark:border-amber-500 dark:bg-amber-950 dark:text-amber-50";
    message = "Pay sends test sats on Blink staging. No real money moves.";
  } else if (live) {
    tone = "border-red-700 bg-red-100 text-red-950 dark:border-red-500 dark:bg-red-950 dark:text-red-50";
    message = `Payouts go to an unrecognised API (${status.api_host}). Check BLINK_API_URL before paying anything.`;
  } else {
    tone = "border-zinc-400 bg-zinc-100 text-zinc-900 dark:border-zinc-600 dark:bg-zinc-900 dark:text-zinc-100";
    message = `Pay is unavailable: ${status.problem ?? "payouts are disabled."} Payments can still be recorded by hand.`;
  }

  const pill = "rounded px-2 py-0.5 font-mono text-xs font-bold tracking-wide";
  return (
    <div role="status" className={`flex flex-col gap-2 rounded border-2 p-3 ${tone}`}>
      <div className="flex flex-wrap gap-2">
        <span className={`${pill} ${live ? "bg-current/15" : "bg-current/10"}`}>
          PAYOUTS {status.enabled ? "ON" : "OFF"}
        </span>
        <span className={`${pill} bg-current/10`}>{network}</span>
      </div>
      <p className="text-sm font-medium">{message}</p>
    </div>
  );
}
