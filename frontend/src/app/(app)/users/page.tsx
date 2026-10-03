import { notFound } from "next/navigation";
import { muted } from "@/components/ui";
import { backendGet } from "@/lib/backend";
import type { AdminUser, Me } from "@/lib/types";
import { UserList } from "./user-list";

export default async function UsersPage() {
  const me = await backendGet<Me>("/auth/me");
  // Admins only; everyone else gets the same 404 as any unknown page
  if (!me.is_admin) notFound();

  const users = await backendGet<AdminUser[]>("/users"); // newest first

  return (
    <main className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-xl font-semibold">Users</h1>
        <p className={`text-sm ${muted}`}>
          Blocking signs a user out and stops them signing in. Everything they contributed is kept, and
          unblocking restores their access.
        </p>
      </header>
      <UserList initialUsers={users} currentUserId={me.id} />
    </main>
  );
}
