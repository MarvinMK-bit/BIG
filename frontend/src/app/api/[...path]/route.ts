import type { NextRequest } from "next/server";
import { API_BASE, TOKEN_COOKIE } from "@/lib/config";

// These return a JWT in the response body; the browser must only get it via the httpOnly cookie
// set by /auth/login, so they are not reachable through the proxy.
const TOKEN_ENDPOINTS = new Set(["auth/login", "auth/register"]);

// Hop-by-hop / connection-specific headers that must not be forwarded.
const STRIP_REQUEST = ["host", "connection", "cookie", "authorization", "content-length"];
const STRIP_RESPONSE = ["connection", "transfer-encoding", "content-encoding", "content-length"];

async function forward(request: NextRequest, ctx: RouteContext<"/api/[...path]">) {
  const { path } = await ctx.params;
  const target = path.join("/");
  if (TOKEN_ENDPOINTS.has(target.replace(/\/+$/, "").toLowerCase())) {
    return Response.json({ detail: "Not found" }, { status: 404 });
  }

  const headers = new Headers(request.headers);
  for (const name of STRIP_REQUEST) headers.delete(name);
  const token = request.cookies.get(TOKEN_COOKIE)?.value;
  if (token) headers.set("authorization", `Bearer ${token}`);

  const hasBody = request.method !== "GET" && request.method !== "HEAD" && request.body !== null;
  const init: RequestInit & { duplex?: "half" } = {
    method: request.method,
    headers,
    redirect: "manual",
    cache: "no-store",
  };
  if (hasBody) {
    init.body = request.body;
    init.duplex = "half";
  }

  let upstream: Response;
  try {
    upstream = await fetch(`${API_BASE}/${target}${request.nextUrl.search}`, init);
  } catch {
    return Response.json({ detail: "Backend unavailable" }, { status: 502 });
  }

  const responseHeaders = new Headers(upstream.headers);
  for (const name of STRIP_RESPONSE) responseHeaders.delete(name);
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  });
}

export {
  forward as GET,
  forward as POST,
  forward as PATCH,
  forward as DELETE,
};
