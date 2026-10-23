import { describe, expect, it } from "vitest";
import type { NextRequest } from "next/server";
import { middleware } from "@/middleware";

function createMockRequest(urlStr: string, cookies: Record<string, string> = {}): NextRequest {
  const url = new URL(urlStr);
  return {
    url: urlStr,
    nextUrl: url,
    cookies: {
      has: (name: string) => name in cookies,
      get: (name: string) => (name in cookies ? { name, value: cookies[name] } : undefined),
    },
  } as unknown as NextRequest;
}

describe("Route Protection Middleware (middleware.ts)", () => {
  it("redirects unauthenticated requests from /dashboard to /login?from=/dashboard", () => {
    const request = createMockRequest("http://localhost:3000/dashboard");
    const response = middleware(request);

    expect(response.status).toBe(307);
    const location = response.headers.get("location");
    expect(location).toBe("http://localhost:3000/login?from=%2Fdashboard");
  });

  it("redirects unauthenticated requests from /runs to /login?from=/runs/new", () => {
    const request = createMockRequest("http://localhost:3000/runs/new");
    const response = middleware(request);

    expect(response.status).toBe(307);
    const location = response.headers.get("location");
    expect(location).toBe("http://localhost:3000/login?from=%2Fruns%2Fnew");
  });

  it("preserves query parameters in redirect 'from' param", () => {
    const request = createMockRequest("http://localhost:3000/dashboard?view=grid&sort=desc");
    const response = middleware(request);

    expect(response.status).toBe(307);
    const location = response.headers.get("location");
    expect(location).toBe("http://localhost:3000/login?from=%2Fdashboard%3Fview%3Dgrid%26sort%3Ddesc");
  });

  it("allows unauthenticated access to /login and /signup", () => {
    const loginReq = createMockRequest("http://localhost:3000/login");
    const loginRes = middleware(loginReq);
    expect(loginRes.status).toBe(200);

    const signupReq = createMockRequest("http://localhost:3000/signup");
    const signupRes = middleware(signupReq);
    expect(signupRes.status).toBe(200);
  });

  it("allows unauthenticated access to public share routes (/share/[token] and /s/[token])", () => {
    const shareReq = createMockRequest("http://localhost:3000/share/sample-unguessable-token-123");
    const shareRes = middleware(shareReq);
    expect(shareRes.status).toBe(200);

    const shortShareReq = createMockRequest("http://localhost:3000/s/short-token-456");
    const shortShareRes = middleware(shortShareReq);
    expect(shortShareRes.status).toBe(200);
  });

  it("allows authenticated requests to access public share routes without redirect", () => {
    const shareReq = createMockRequest("http://localhost:3000/share/sample-token", {
      krama_session: "demo-session-token",
    });
    const shareRes = middleware(shareReq);
    expect(shareRes.status).toBe(200);
  });

  it("allows authenticated requests with krama_session to access /dashboard and /runs", () => {
    const dashboardReq = createMockRequest("http://localhost:3000/dashboard", {
      krama_session: "demo-session-token",
    });
    const dashboardRes = middleware(dashboardReq);
    expect(dashboardRes.status).toBe(200);

    const runsReq = createMockRequest("http://localhost:3000/runs", {
      krama_session: "demo-session-token",
    });
    const runsRes = middleware(runsReq);
    expect(runsRes.status).toBe(200);
  });

  it("redirects authenticated users away from /login and /signup to /dashboard", () => {
    const loginReq = createMockRequest("http://localhost:3000/login", {
      krama_session: "demo-session-token",
    });
    const loginRes = middleware(loginReq);

    expect(loginRes.status).toBe(307);
    expect(loginRes.headers.get("location")).toBe("http://localhost:3000/dashboard");

    const signupReq = createMockRequest("http://localhost:3000/signup", {
      krama_session: "demo-session-token",
    });
    const signupRes = middleware(signupReq);

    expect(signupRes.status).toBe(307);
    expect(signupRes.headers.get("location")).toBe("http://localhost:3000/dashboard");
  });
});
