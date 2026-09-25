import { notFound } from "next/navigation";
import { muted } from "@/components/ui";
import { backendGet } from "@/lib/backend";
import type { Feedback, Me } from "@/lib/types";
import { ModerationList } from "./moderation-list";

export default async function ModerationPage() {
  const me = await backendGet<Me>("/auth/me");
  // Admins only; everyone else gets the same 404 as any unknown page
  if (!me.is_admin) notFound();

  const pending = await backendGet<Feedback[]>("/feedback/pending");
  const newestFirst = pending.toSorted((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));

  return (
    <main className="flex flex-col gap-4">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">Moderation</h1>
        <p className={`text-sm ${muted}`}>
          Feedback awaiting review. Approved items appear publicly; rejected and muted ones don&apos;t.
        </p>
      </header>
      <ModerationList initialItems={newestFirst} />
    </main>
  );
}
