import { cookies } from "next/headers";
import { API_BASE, TOKEN_COOKIE } from "@/lib/config";

// Seconds until the JWT's `exp`, so the cookie lives exactly as long as the token.
function tokenMaxAge(jwt: string): number | undefined {
  try {
    const payload = JSON.parse(Buffer.from(jwt.split(".")[1], "base64url").toString());
    const seconds = Math.floor(payload.exp - Date.now() / 1000);
    return seconds > 0 ? seconds : undefined;
  } catch {
    return undefined;
  }
}

function errorMessage(body: unknown): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" ? detail : "Login failed";
}

export async function POST(request: Request) {
  let form: FormData;
  try {
    form = await request.formData();
  } catch {
    return Response.json({ detail: "Invalid form data" }, { status: 400 });
  }

  const body = new URLSearchParams();
  for (const key of ["username", "password"]) {
    const value = form.get(key);
    if (typeof value === "string") body.set(key, value);
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE}/auth/login`, { method: "POST", body, cache: "no-store" });
  } catch {
    return Response.json({ detail: "Backend unavailable" }, { status: 502 });
  }

  const data = await upstream.json().catch(() => null);
  if (!upstream.ok || typeof data?.access_token !== "string") {
    return Response.json(
      { detail: errorMessage(data) },
      { status: upstream.ok ? 502 : upstream.status },
    );
  }

  (await cookies()).set(TOKEN_COOKIE, data.access_token, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: tokenMaxAge(data.access_token),
  });
  return Response.json({ ok: true });
}
