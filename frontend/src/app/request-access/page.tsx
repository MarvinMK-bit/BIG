"use client";

import Link from "next/link";
import { useState } from "react";
import { muted } from "@/components/ui";
import { apiRequest } from "@/lib/api-client";
import { isWaking, WAKING_MESSAGE } from "@/lib/waking";

const input = "rounded border border-zinc-400 bg-transparent px-3 py-2";

export default function RequestAccessPage() {
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [received, setReceived] = useState<string | null>(null);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const field = (name: string) => String(form.get(name) ?? "").trim();
    if (!field("email") && !field("phone")) {
      setError("Give an email address or a phone number so we can contact you.");
      return;
    }
    setError(null);
    setPending(true);
    const result = await apiRequest<{ message: string }>("/api/auth/request-access", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        username: field("username"),
        // Not trimmed: spaces are part of a password
        password: String(form.get("password") ?? ""),
        display_name: field("display_name") || null,
        email: field("email") || null,
        phone: field("phone") || null,
        about: field("about"),
      }),
    });
    setPending(false);
    if (result.ok) return setReceived(result.data.message);
    setError(isWaking(result.status) ? WAKING_MESSAGE : result.error);
  }

  if (received) {
    return (
      <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-4 p-6">
        <h1 className="text-2xl font-semibold">Request received</h1>
        <p role="status">{received}</p>
        <p className={`text-sm ${muted}`}>
          There is nothing more to do for now. Each request is read by a person, so it may take a few days.
        </p>
        <Link href="/login" className="text-sm underline">
          Back to sign in
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-4 p-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold">Request an account</h1>
        <p className={`text-sm ${muted}`}>
          Accounts on this instance are approved by hand. Choose your sign-in details now; you can use
          them once your request is approved.
        </p>
      </header>
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Username
          <input name="username" autoComplete="username" required minLength={3} maxLength={50} className={input} />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            maxLength={72}
            className={input}
          />
          <span className={`text-xs ${muted}`}>At least 8 characters.</span>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Display name (optional)
          <input name="display_name" autoComplete="name" maxLength={100} className={input} />
        </label>
        <fieldset className="flex flex-col gap-3">
          <legend className="mb-1 text-sm">
            How to reach you <span className={muted}>— an email address, a phone number, or both</span>
          </legend>
          <label className="flex flex-col gap-1 text-sm">
            Email
            <input name="email" type="email" autoComplete="email" className={input} />
          </label>
          <label className="flex flex-col gap-1 text-sm">
            Phone
            <input name="phone" type="tel" autoComplete="tel" placeholder="+44 7700 900123" className={input} />
          </label>
        </fieldset>
        <label className="flex flex-col gap-1 text-sm">
          About you
          <textarea name="about" required maxLength={2000} rows={4} className={input} />
          <span className={`text-xs ${muted}`}>Who you are, and what you would like to use BIG for.</span>
        </label>
        {error && (
          <p role="alert" className="text-sm text-red-600">
            {error}
          </p>
        )}
        <button
          type="submit"
          disabled={pending}
          className="rounded bg-foreground px-3 py-2 text-background disabled:opacity-50"
        >
          {pending ? "Sending…" : "Request access"}
        </button>
      </form>
      <p className="text-sm">
        Already have an account?{" "}
        <Link href="/login" className="underline">
          Sign in
        </Link>
      </p>
    </main>
  );
}
