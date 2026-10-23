import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PREFIXES = ["/dashboard", "/runs"];
const PUBLIC_PREFIXES = ["/share", "/s", "/login", "/signup"];
const AUTH_COOKIE_NAME = "krama_session";

export function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl;
  const hasSession = request.cookies.has(AUTH_COOKIE_NAME);

  // Whitelisted public routes bypass protection checks
  const isPublicRoute = PUBLIC_PREFIXES.some((prefix) => pathname.startsWith(prefix));
  if (isPublicRoute) {
    const isAuthRoute = pathname === "/login" || pathname === "/signup";
    if (isAuthRoute && hasSession) {
      return NextResponse.redirect(new URL("/dashboard", request.url));
    }
    return NextResponse.next();
  }

  const isProtected = PROTECTED_PREFIXES.some((prefix) => pathname.startsWith(prefix));

  if (isProtected && !hasSession) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", `${pathname}${search}`);
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/dashboard/:path*",
    "/runs/:path*",
    "/login",
    "/signup",
    "/share/:path*",
    "/s/:path*",
  ],
};
