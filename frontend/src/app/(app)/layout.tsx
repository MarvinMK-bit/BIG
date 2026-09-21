import Link from "next/link";
import { backendGet } from "@/lib/backend";
import { LogoutButton } from "./logout-button";

export default async function AppLayout({ children }: { children: React.ReactNode }) {
  const user = await backendGet<{ username: string }>("/auth/me");

  return (
    <>
      <header className="border-b border-zinc-300 dark:border-zinc-700">
        <div className="mx-auto flex w-full max-w-3xl flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
          <nav className="flex items-center gap-4 text-sm">
            <Link href="/dashboard" className="font-semibold">
              BIG
            </Link>
            <Link href="/accuracy" className="underline">
              Accuracy
            </Link>
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
