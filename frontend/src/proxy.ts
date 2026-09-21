import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const TOKEN_COOKIE = "big_token";

// Reachable without a session. The login page needs the config to decide whether to show sign-up.
const PUBLIC_EXACT = new Set(["/", "/login", "/api/auth/config"]);

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const isPublic =
    PUBLIC_EXACT.has(pathname) || pathname === "/auth" || pathname.startsWith("/auth/");
  if (isPublic || request.cookies.has(TOKEN_COOKIE)) return NextResponse.next();

  // API callers can't follow a redirect to an HTML page meaningfully.
  if (pathname.startsWith("/api/")) {
    return Response.json({ detail: "Not authenticated" }, { status: 401 });
  }
  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  // Skip Next internals and static files in /public (anything with a file extension).
  matcher: ["/((?!_next/static|_next/image|favicon\\.ico|.*\\.[^/]+$).*)"],
};
