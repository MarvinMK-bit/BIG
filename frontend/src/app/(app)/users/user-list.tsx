"use client";

import { useState } from "react";
import { RelativeTime } from "@/components/relative-time";
import { muted } from "@/components/ui";
import { apiRequest } from "@/lib/api-client";
import type { AdminUser } from "@/lib/types";

export function UserList({ initialUsers, currentUserId }: { initialUsers: AdminUser[]; currentUserId: string }) {
  const [users, setUsers] = useState(initialUsers);
  // The user whose block or unblock is awaiting confirmation
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function setActive(user: AdminUser, isActive: boolean) {
    setBusy(user.id);
    setErrors((e) => ({ ...e, [user.id]: "" }));
    const result = await apiRequest<AdminUser>(`/api/users/${user.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ is_active: isActive }),
    });
    setBusy(null);
    setConfirming(null);
    if (!result.ok) return setErrors((e) => ({ ...e, [user.id]: result.error }));
    setUsers((list) => list.map((u) => (u.id === user.id ? result.data : u)));
  }

  return (
    <ol className="flex flex-col divide-y divide-zinc-200 rounded border border-zinc-300 dark:divide-zinc-800 dark:border-zinc-700">
      {users.map((user) => {
        const blocking = user.is_active; // what the action would do
        return (
          <li key={user.id} className={`flex flex-col gap-2 p-3 ${user.is_active ? "" : "bg-red-50 dark:bg-red-950/30"}`}>
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex min-w-0 flex-col gap-0.5">
                <p className="flex flex-wrap items-baseline gap-x-2">
                  <span className="break-all font-medium">{user.username}</span>
                  {user.display_name && <span className="text-sm">{user.display_name}</span>}
                  {user.is_admin && <span className={`text-xs ${muted}`}>admin</span>}
                  {!user.is_active && (
                    <span className="text-xs font-medium text-red-700 dark:text-red-400">blocked</span>
                  )}
                </p>
                <p className={`text-xs ${muted}`}>
                  {user.email && <span className="break-all">{user.email} · </span>}
                  joined <RelativeTime iso={user.created_at} />
                </p>
              </div>
              {user.id === currentUserId ? (
                <span className={`text-xs ${muted}`}>you</span>
              ) : confirming !== user.id ? (
                <button
                  onClick={() => setConfirming(user.id)}
                  disabled={busy !== null}
                  className={`min-h-11 shrink-0 rounded border px-4 text-sm disabled:opacity-50 ${
                    blocking
                      ? "border-red-600 text-red-700 dark:text-red-400"
                      : "border-green-700 text-green-800 dark:border-green-500 dark:text-green-300"
                  }`}
                >
                  {blocking ? "Block" : "Unblock"}
                </button>
              ) : null}
            </div>

            {confirming === user.id && (
              <div role="alertdialog" aria-label={`${blocking ? "Block" : "Unblock"} ${user.username}`} className="flex flex-col gap-2 rounded border border-zinc-300 p-3 text-sm dark:border-zinc-700">
                <p>
                  {blocking ? (
                    <>
                      Block <span className="font-medium">{user.username}</span>? They will be signed out and
                      unable to sign in. Their contributions are kept.
                    </>
                  ) : (
                    <>
                      Unblock <span className="font-medium">{user.username}</span>? They will be able to sign in
                      again.
                    </>
                  )}
                </p>
                <div className="flex flex-wrap gap-2">
                  <button
                    onClick={() => setActive(user, !blocking)}
                    disabled={busy !== null}
                    className="min-h-11 rounded bg-foreground px-4 text-background disabled:opacity-50"
                  >
                    {busy === user.id ? "…" : `${blocking ? "Block" : "Unblock"} ${user.username}`}
                  </button>
                  <button
                    onClick={() => setConfirming(null)}
                    disabled={busy !== null}
                    className="min-h-11 rounded border border-zinc-400 px-4 disabled:opacity-50"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {errors[user.id] && (
              <p role="alert" className="text-sm text-red-600">
                {errors[user.id]}
              </p>
            )}
          </li>
        );
      })}
    </ol>
  );
}
