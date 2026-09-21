"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const [registrationOpen, setRegistrationOpen] = useState(false);

  // Hidden unless the backend says registration is open (also hidden if the request fails).
  useEffect(() => {
    fetch("/api/auth/config")
      .then((res) => (res.ok ? res.json() : null))
      .then((config) => setRegistrationOpen(config?.registration_open === true))
      .catch(() => {});
  }, []);

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setPending(true);
    try {
      const res = await fetch("/auth/login", {
        method: "POST",
        body: new FormData(event.currentTarget),
      });
      if (res.ok) {
        router.push("/dashboard");
        router.refresh();
        return;
      }
      const body = await res.json().catch(() => null);
      setError(typeof body?.detail === "string" ? body.detail : "Login failed");
    } catch {
      setError("Could not reach the server");
    }
    setPending(false);
  }

  return (
    <main className="mx-auto flex w-full max-w-sm flex-1 flex-col justify-center gap-4 p-6">
      <h1 className="text-2xl font-semibold">Sign in</h1>
      <form onSubmit={onSubmit} className="flex flex-col gap-3">
        <label className="flex flex-col gap-1 text-sm">
          Username
          <input
            name="username"
            autoComplete="username"
            required
            className="rounded border border-zinc-400 bg-transparent px-3 py-2"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Password
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className="rounded border border-zinc-400 bg-transparent px-3 py-2"
          />
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
          {pending ? "Signing in…" : "Sign in"}
        </button>
      </form>
      {registrationOpen && (
        <p className="text-sm">
          No account?{" "}
          <Link href="/register" className="underline">
            Sign up
          </Link>
        </p>
      )}
    </main>
  );
}
