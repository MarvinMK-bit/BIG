"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { RelativeTime } from "@/components/relative-time";
import { muted } from "@/components/ui";
import { apiRequest } from "@/lib/api-client";
import type { AccessRequest, AccessRequestStatus } from "@/lib/types";

type Decision = Exclude<AccessRequestStatus, "pending">;

const ACTIONS: { status: Decision; label: string; className: string }[] = [
  { status: "approved", label: "Approve", className: "border-green-700 text-green-800 dark:border-green-500 dark:text-green-300" },
  { status: "declined", label: "Decline", className: "border-red-600 text-red-700 dark:text-red-400" },
];

function Applicant({ request }: { request: AccessRequest }) {
  return (
    <header className="flex flex-col gap-1">
      <p className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <span className="break-all font-medium">{request.username}</span>
        {request.display_name && <span className="text-sm">{request.display_name}</span>}
        <span className={`text-xs ${muted}`}>
          <RelativeTime iso={request.created_at} />
        </span>
      </p>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 text-sm">
        {request.email && (
          <>
            <dt className={muted}>Email</dt>
            <dd className="break-all">
              <a href={`mailto:${request.email}`} className="underline">
                {request.email}
              </a>
            </dd>
          </>
        )}
        {request.phone && (
          <>
            <dt className={muted}>Phone</dt>
            <dd className="break-all">
              <a href={`tel:${request.phone.replace(/[^0-9+]/g, "")}`} className="underline">
                {request.phone}
              </a>
            </dd>
          </>
        )}
      </dl>
      <p className="whitespace-pre-wrap break-words text-sm">{request.about}</p>
    </header>
  );
}

export function AccessRequestList({ initialItems }: { initialItems: AccessRequest[] }) {
  const router = useRouter();
  const [, startTransition] = useTransition();
  // Decided requests stay on screen, in place, after the refresh that updates the nav badge
  const [decided, setDecided] = useState<Record<string, AccessRequest>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});

  async function decide(request: AccessRequest, status: Decision) {
    setBusy(request.id);
    setErrors((e) => ({ ...e, [request.id]: "" }));
    const result = await apiRequest<AccessRequest>(`/api/access-requests/${request.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, note: notes[request.id]?.trim() || null }),
    });
    setBusy(null);
    if (!result.ok) return setErrors((e) => ({ ...e, [request.id]: result.error }));
    setDecided((d) => ({ ...d, [request.id]: result.data }));
    startTransition(() => router.refresh());
  }

  const pending = initialItems.filter((r) => r.status === "pending" || decided[r.id]);
  const pendingIds = new Set(pending.map((r) => r.id));
  const items = [...pending, ...Object.values(decided).filter((r) => !pendingIds.has(r.id))];
  const earlier = initialItems.filter((r) => r.status !== "pending" && !decided[r.id]);

  return (
    <div className="flex flex-col gap-3">
      {items.length === 0 ? (
        <p className={`text-sm ${muted}`}>No access requests awaiting review.</p>
      ) : (
        <ol className="flex flex-col gap-3">
          {items.map((request) => {
            const outcome = decided[request.id];
            return (
              <li
                key={request.id}
                className={`flex flex-col gap-3 rounded border border-zinc-300 p-3 dark:border-zinc-700 ${
                  outcome?.status === "declined" ? "opacity-60" : ""
                }`}
              >
                <Applicant request={request} />

                {outcome?.status === "approved" ? (
                  <p role="status" className="text-sm font-medium text-green-800 dark:text-green-300">
                    Approved — {request.username} can now sign in. Let them know on the{" "}
                    {request.email ? "email" : "phone number"} they gave.
                  </p>
                ) : outcome ? (
                  <p role="status" className="text-sm font-medium">
                    Declined
                  </p>
                ) : (
                  <div className="flex flex-col gap-2">
                    <label className="flex flex-col gap-1 text-sm">
                      Note (optional, for admins only)
                      <textarea
                        value={notes[request.id] ?? ""}
                        onChange={(e) => setNotes((n) => ({ ...n, [request.id]: e.target.value }))}
                        disabled={busy !== null}
                        maxLength={2000}
                        rows={2}
                        className="rounded border border-zinc-400 bg-background px-3 py-2 text-base"
                      />
                    </label>
                    <div className="flex flex-wrap gap-2">
                      {ACTIONS.map((action) => (
                        <button
                          key={action.status}
                          onClick={() => decide(request, action.status)}
                          disabled={busy !== null}
                          className={`min-h-11 flex-1 rounded border px-4 text-sm disabled:opacity-50 sm:flex-none ${action.className}`}
                        >
                          {busy === request.id ? "…" : action.label}
                        </button>
                      ))}
                    </div>
                  </div>
                )}

                {errors[request.id] && (
                  <p role="alert" className="text-sm text-red-600">
                    {errors[request.id]}
                  </p>
                )}
              </li>
            );
          })}
        </ol>
      )}

      {earlier.length > 0 && (
        <details>
          <summary className={`cursor-pointer text-sm ${muted}`}>Earlier requests ({earlier.length})</summary>
          <ul className="mt-2 flex flex-col divide-y divide-zinc-200 rounded border border-zinc-300 text-sm dark:divide-zinc-800 dark:border-zinc-700">
            {earlier.map((r) => (
              <li key={r.id} className="flex flex-col gap-0.5 p-2">
                <p className="flex flex-wrap items-baseline gap-x-2">
                  <span className="break-all font-medium">{r.username}</span>
                  <span className={r.status === "approved" ? "text-green-800 dark:text-green-300" : muted}>
                    {r.status}
                  </span>
                  {r.reviewed_at && (
                    <span className={`text-xs ${muted}`}>
                      <RelativeTime iso={r.reviewed_at} />
                    </span>
                  )}
                </p>
                {r.review_note && <p className={`whitespace-pre-wrap break-words text-xs ${muted}`}>{r.review_note}</p>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
