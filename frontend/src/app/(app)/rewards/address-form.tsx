"use client";

import { useRouter } from "next/navigation";
import { useId, useState, useTransition } from "react";
import { muted } from "@/components/ui";
import { apiRequest } from "@/lib/api-client";
import type { Me } from "@/lib/types";

export function AddressForm({ initial }: { initial: string | null }) {
  const id = useId();
  const router = useRouter();
  const [, startTransition] = useTransition();
  const [value, setValue] = useState(initial ?? "");
  const [saved, setSaved] = useState(initial);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    const result = await apiRequest<Me>("/api/auth/me", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ blink_address: value.trim() || null }),
    });
    setSaving(false);
    if (!result.ok) return setError(result.error);
    setSaved(result.data.blink_address);
    setValue(result.data.blink_address ?? "");
    startTransition(() => router.refresh());
  }

  const unchanged = (value.trim().toLowerCase() || null) === saved;

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <label htmlFor={id} className="text-sm font-medium">
        Your Lightning address
      </label>
      <p className={`text-xs ${muted}`}>
        Rewards can&apos;t be paid without one. It looks like an email address, e.g. alice@blink.sv.
      </p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          id={id}
          type="text"
          inputMode="email"
          autoCapitalize="none"
          autoCorrect="off"
          spellCheck={false}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="name@domain"
          maxLength={320}
          className="min-h-11 w-full rounded border border-zinc-400 bg-transparent px-3 text-base sm:text-sm dark:border-zinc-600"
        />
        <button
          type="submit"
          disabled={saving || unchanged}
          className="min-h-11 shrink-0 rounded bg-foreground px-4 text-sm text-background disabled:opacity-50"
        >
          {saving ? "Saving…" : value.trim() ? "Save address" : "Remove address"}
        </button>
      </div>
      <p role="status" className={`text-xs ${muted}`}>
        {saved ? `Saved: ${saved}` : "No address saved."}
      </p>
      {error && (
        <p role="alert" className="text-sm text-red-600">
          {error}
        </p>
      )}
    </form>
  );
}
