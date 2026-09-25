import Link from "next/link";
import { backendGet } from "@/lib/backend";
import type { Feedback, Me } from "@/lib/types";
import { LogoutButton } from "./logout-button";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await backendGet<Me>("/auth/me");
  const pendingCount = user.is_admin
    ? (await backendGet<Feedback[]>("/feedback/pending")).length
    : 0;

  return (
    <>
      <header className="border-b border-zinc-300 dark:border-zinc-700">
        <div className="mx-auto flex w-full max-w-3xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
          <nav className="flex flex-wrap items-center gap-x-4 gap-y-2 text-sm">
            <Link href="/dashboard" className="font-semibold">
              BIG
            </Link>
            <Link href="/schemes" className="underline">
              Mark schemes
            </Link>
            <Link href="/accuracy" className="underline">
              Accuracy
            </Link>
            <Link href="/rewards" className="underline">
              Rewards
            </Link>
            {user.is_admin && (
              <Link href="/guides" className="underline">
                Guides
              </Link>
            )}
            {user.is_admin && (
              <Link href="/moderation" className="flex items-center gap-1.5 underline">
                Moderation
                {pendingCount > 0 && (
                  <span
                    aria-label={`${pendingCount} pending`}
                    className="rounded-full bg-amber-200 px-1.5 text-xs font-medium text-amber-900 no-underline dark:bg-amber-900 dark:text-amber-100"
                  >
                    {pendingCount}
                  </span>
                )}
              </Link>
            )}
          </nav>
          <div className="flex items-center gap-3 text-sm">
            <span>Signed in as {user.username}</span>
            <LogoutButton />
          </div>
        </div>
      </header>
      <div className="mx-auto w-full max-w-3xl flex-1 px-4 py-6">{children}</div>
    </>
  );
}
