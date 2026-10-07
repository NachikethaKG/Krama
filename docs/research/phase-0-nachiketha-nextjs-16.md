# Next.js 16 App Router: what changed, client vs server, where fetch and EventSource live

- **Phase:** 0
- **Researched by:** Nachiketha (research done by Claude Code on Vishwas's laptop with Nachiketha present; decisions by Nachiketha)
- **Question(s):** Next.js 16 App Router: read `frontend/node_modules/next/dist/docs/` (version 16 changed a lot). Also: client vs server components, and where `fetch` and `EventSource` should live.

## Findings
Installed: **next 16.3.8**, **react 19.2.8** (`frontend/package.json`). All doc paths below are under `frontend/node_modules/next/dist/docs/01-app/`.

**What changed in 16** [verified: `02-guides/upgrading/version-16.md`]
- **Async request APIs only.** "Starting with Next.js 16, synchronous access is fully removed": `params`, `searchParams`, `cookies()`, `headers()`, `draftMode()` must be awaited. `next typegen` generates `PageProps<'/route'>` / `LayoutProps` types.
- **Turbopack is the default** for `next dev` and `next build`. A custom `webpack` config makes `next build` fail; `--webpack` opts out.
- **`middleware` is deprecated in favour of `proxy`** (`proxy.ts`). It runs on the Node.js runtime [verified: also `03-api-reference/03-file-conventions/proxy.md`].
- **Partial prerendering comes from `cacheComponents: true`**, which is opt-in. `experimental.dynamicIO` and `experimental.useCache` are gone [verified: `03-api-reference/05-config/01-next-config-js/cacheComponents.md`].
- **React Compiler** support is stable but off by default.
- **Removed:** AMP, `next lint` (use the ESLint CLI with flat config), `serverRuntimeConfig` / `publicRuntimeConfig`. Parallel-route slots now need a `default.js`.

**Caching**
- `fetch` responses are **not cached by default**; caching is opted into with `'use cache'` + `cacheLife`, and uncached reads are wrapped in `<Suspense>` [verified: `01-getting-started/06-fetching-data.md`, `08-caching.md`]
- "Route Handlers are not cached by default" [verified: `01-getting-started/15-route-handlers.md`]

**Server vs client components** [verified: `01-getting-started/05-server-and-client-components.md`, `03-api-reference/01-directives/use-client.md`, `02-guides/environment-variables.md`]
- Components are Server Components unless a file starts with `'use client'`. State, event handlers, effects (`useEffect`) and browser APIs (`window`, `EventSource`, `localStorage`) need a client component.
- `'use client'` marks a boundary: everything the file imports becomes client code. Server Components passed in as `children` stay on the server.
- Props that cross the boundary must be serializable: no functions, no class instances.
- Only `NEXT_PUBLIC_*` env variables reach the browser, inlined at **build** time. `import 'server-only'` guards server-only modules.

**Streaming / SSE** [verified: `02-guides/streaming.md`, `02-guides/backend-for-frontend.md`]
- A Route Handler can stream a raw `ReadableStream` response (works for SSE), and can proxy to another backend.
- Nginx-style reverse proxies buffer by default; set `X-Accel-Buffering: no`.

**Our frontend today** [verified locally: read `frontend/app/page.tsx`, `frontend/components/api-status.tsx`, `frontend/lib/api.ts`, `frontend/next.config.ts`]
- `app/page.tsx` is a Server Component rendering the client component `ApiStatus`, which calls `createApiClient()` in `useEffect`.
- `lib/api.ts` has the `ApiClient` seam with `HttpApiClient` and `MockApiClient`; `next.config.ts` loads the repo-root `.env`.
- This already follows the rules above.

## Recommendation
Proposed (pending Nachiketha's decision):
- **Live run view (#41): `EventSource` lives only in client code**, behind the existing `ApiClient.runEvents()` async iterator (the Phase F decision). The component consumes it with `for await` inside `useEffect`, passes an `AbortController` signal, and calls `abort()` in the cleanup. React StrictMode mounts twice in dev, so the cleanup must really close the stream.
- **`HttpApiClient` wraps `EventSource`** (or `fetch` + a stream reader) in an async generator, so mock and http modes look the same to the UI.
- **Same-origin API calls:** proxy `/api/v1/*` to FastAPI with a `rewrites()` entry in `next.config.ts` (or a small streaming Route Handler if rewrites buffer SSE), so there is no CORS setup. Don't use `proxy.ts` for this; it's for request interception.
- **Server Components for one-off reads** (e.g. loading a workflow for a tutorial page): an async page with `await params` and `<Suspense>`, **no `'use cache'`**, because runs are live data. Never pass an `ApiClient` instance from a Server Component to a client component (not serializable).
- **Leave `cacheComponents` and the React Compiler off** in Phase 0.

## Open questions
- `NEXT_PUBLIC_API_MODE` is fixed at build time. Is that fine for the demo, or do we need a runtime switch between mock and live?
- Check whether `rewrites()` streams SSE without buffering once the real backend SSE endpoint exists (#41 / Phase 1).

## Links
- `frontend/node_modules/next/dist/docs/01-app/02-guides/upgrading/version-16.md`
- `frontend/node_modules/next/dist/docs/01-app/01-getting-started/05-server-and-client-components.md`
- `frontend/node_modules/next/dist/docs/01-app/02-guides/streaming.md`
- https://nextjs.org/docs/app
