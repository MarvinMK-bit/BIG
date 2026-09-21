// Browser-side helpers for calling the /api proxy.

type ApiResult<T> = { ok: true; data: T } | { ok: false; error: string };

// FastAPI `detail` is a string for most errors and a list of {msg} for 422 validation errors.
function detailMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const msgs = detail.map((d) => (d as { msg?: unknown })?.msg).filter((m) => typeof m === "string");
    if (msgs.length) return msgs.join("; ");
  }
  if (status === 413) return "File is too large";
  return `Request failed (${status})`;
}

export async function apiRequest<T>(url: string, init: RequestInit): Promise<ApiResult<T>> {
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    return { ok: false, error: "Could not reach the server" };
  }
  const body = await res.json().catch(() => null);
  if (!res.ok) return { ok: false, error: detailMessage(body, res.status) };
  return { ok: true, data: body as T };
}

export function postJson<T>(url: string, body?: unknown) {
  return apiRequest<T>(url, {
    method: "POST",
    headers: body === undefined ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}
