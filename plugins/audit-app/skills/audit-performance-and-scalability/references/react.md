# React (and Next.js) reference for audit-performance-and-scalability

Scope here is runtime behaviour: render-blocking resources, API calls per page
and duplicates, client caching, images, re-renders, Core Web Vitals. Bundle,
code splitting and lint-level hygiene are `audit-frontend-best-practices`.
For Next.js, server-side code (`app/api`, server components, server actions)
is a Node backend - apply `node-express.md` to it.

## Stack markers
`package.json` with `react`, `react-dom`; `next` (App Router `app/` vs Pages `pages/`), `remix`, `vite`. Data layer: `@tanstack/react-query`, `swr`, `@reduxjs/toolkit` (RTK Query), `apollo`, or bare `fetch` in `useEffect` (no caching, no dedup).

## Where the relevant code lives
`index.html`/`app/layout.tsx`/`pages/_document.tsx` (blocking scripts, fonts, `<Script strategy>`), `main.tsx`/`app/providers.tsx` (QueryClient defaults: `staleTime`), page components (`useEffect` fetch fan-out), hooks (`useProducts()` called in many components), `next.config.js` (`images`, `compress`, `headers`), `public/` images, components with `useMemo`/`useCallback` gaps and inline object props.

## Dangerous / interesting APIs and patterns
- RENDER-BLOCK: `<script src>` in `<head>` without `defer`/`async`; Next `<Script>` with `strategy="beforeInteractive"` for non-critical scripts; third-party CSS/fonts without `preconnect`; `next/font` not used (self-hosting + `font-display`); no SSR/SSG for public landing pages (LCP waits for JS + data).
- CALLS-PER-PAGE: `useEffect(() => fetch(...), [])` in several components on one page fetching the same URL (no dedup); `useQuery` with `staleTime: 0` (default) re-fetching on every mount and window focus - five widgets = five requests; waterfall fetches (`useEffect` chains: fetch A, then in another effect fetch B); polling `refetchInterval` too aggressive; search inputs without debounce.
- CLIENT-CACHE: bare `fetch`/axios in `useEffect` with no cache layer; React Query/SWR with no `staleTime` for reference data; no `Cache-Control` from the API (cross-check backend); Next `fetch` with `cache: 'no-store'` everywhere; no service worker for GET APIs (Workbox `runtimeCaching`).
- RERENDER: context value objects recreated each render (`<Ctx.Provider value={{a, b}}>`), inline object/array props to memoised children, missing `React.memo` on list rows, `useEffect` setting state that triggers itself, large lists without virtualization (`react-window`/`@tanstack/react-virtual`), state in a top-level component that re-renders the whole tree on keystroke, Redux selectors returning new arrays (`useSelector(s => s.items.filter(...))` without `createSelector`).
- IMAGE: `<img>` instead of `next/image` (or no `width`/`height`, no `loading="lazy"`, no `srcset`); `next.config.js` `images.unoptimized: true`; hero image without `priority`; base64 images in JSON.
- CWV: LCP image not prioritised; CLS from images without dimensions, late-injected banners, fonts swapping; INP from synchronous heavy handlers (`onClick` doing CSV export, big `setState` cascades) without `useTransition`/`useDeferredValue`.

## What "good" looks like
```tsx
const qc = new QueryClient({ defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false } } });
function useProducts(page) { return useQuery({ queryKey: ['products', page], queryFn: () => api.get('/products', { params: { page } }) }); }  // 5 components, 1 request (deduped by key)
const [q, setQ] = useState(''); const dq = useDeferredValue(q); useQuery({ queryKey: ['search', dq], enabled: dq.length > 2 });
const value = useMemo(() => ({ user, setUser }), [user]);
<Image src="/hero.webp" width={1200} height={600} priority alt="..." />
<Script src="https://widget.example/chat.js" strategy="lazyOnload" />
```
Next: `export const revalidate = 300` or `fetch(url, { next: { revalidate: 300, tags: ['products'] } })` + `revalidateTag('products')` on write.

## Manual trace checklist
1. Landing page: enumerate every fetch/`useQuery` on mount across the component tree; duplicates by URL; waterfalls.
2. `QueryClient`/SWR config: `staleTime`, `dedupingInterval`, `refetchOnWindowFocus`.
3. `_document`/`layout`: blocking scripts, fonts, preconnect.
4. Largest list: memoised rows, virtualization, `key` stability.
5. Images: `next/image` or dimensions + lazy + format; LCP `priority`.
6. Lighthouse desktop + mobile on landing + dashboard if a URL exists; record LCP/INP/CLS.

## Stack-specific false positives
- Same `queryKey` used in several components - React Query dedupes; not a duplicate call (verify `staleTime` > 0).
- `<img>` for tiny icons/SVGs.
- `staleTime: 0` for live data (stock levels) - intended; note the polling cost.

## Tooling
React DevTools Profiler ("Highlight updates when components render", flamegraph per interaction), `why-did-you-render` (dev), `npx lighthouse`, Next `experimental.instrumentationHook` / `@vercel/speed-insights`, `web-vitals` library, Chrome DevTools Performance (Interactions for INP), React Query Devtools (see duplicate keys and refetch counts).

## References
web.dev "Core Web Vitals"; React docs "useMemo", "useTransition", "Render and Commit"; TanStack Query "Important Defaults", "Request Waterfalls"; Next.js "Optimizing: Images, Fonts, Scripts", "Caching".
