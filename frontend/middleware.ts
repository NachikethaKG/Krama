// frontend/middleware.ts
import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PREFIXES = ["/dashboard", "/runs", "/settings"];
const PUBLIC_PREFIXES = ["/share", "/s", "/login", "/signup"];
const AUTH_COOKIE_NAME = "krama_session";

function matchesRoutePrefix(pathname: string, prefixes: string[]): boolean {
  return prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;

  // 1. Explicitly allow public whitelisted routes (share tokens, auth)
  const isPublicRoute = matchesRoutePrefix(pathname, PUBLIC_PREFIXES);
  if (isPublicRoute) {
    // If authenticated user navigates to login/signup, bounce to dashboard
    const hasSession = request.cookies.has(AUTH_COOKIE_NAME);
    if ((pathname === "/login" || pathname === "/signup") && hasSession) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
    return NextResponse.next();
  }

  // 2. Protect authenticated application paths
  const isProtected = matchesRoutePrefix(pathname, PROTECTED_PREFIXES);
  const hasSession = request.cookies.has(AUTH_COOKIE_NAME);

  if (isProtected && !hasSession) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", `${pathname}${search}`);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/dashboard/:path*", "/runs/:path*", "/settings/:path*", "/login", "/signup", "/share/:path*", "/s/:path*"],
};
