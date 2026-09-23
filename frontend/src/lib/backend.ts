import { cookies } from "next/headers";
import { notFound, redirect } from "next/navigation";
import { API_BASE, TOKEN_COOKIE } from "@/lib/config";

// Server-side GET against the backend with the session cookie's token. Used by server components;
// the browser goes through the /api proxy instead.
export async function backendGet<T>(path: string, opts: { notFound?: boolean } = {}): Promise<T> {
  return (await backendFetch(path, opts)).json();
}

// Same as backendGet, for endpoints that return plain text.
export async function backendGetText(path: string, opts: { notFound?: boolean } = {}): Promise<string> {
  return (await backendFetch(path, opts)).text();
}

async function backendFetch(path: string, opts: { notFound?: boolean }): Promise<Response> {
  const token = (await cookies()).get(TOKEN_COOKIE)?.value;
  if (!token) redirect("/login");

  const res = await fetch(`${API_BASE}${path}`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  }).catch(() => null);

  if (res?.status === 401) redirect("/login"); // expired or invalid token
  if (opts.notFound && (res?.status === 404 || res?.status === 422)) notFound();
  if (!res?.ok) throw new Error(`Backend request failed: GET ${path}`);
  return res;
}
