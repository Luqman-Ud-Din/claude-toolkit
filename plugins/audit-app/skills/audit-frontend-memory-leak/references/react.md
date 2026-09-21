# React reference for audit-frontend-memory-leak

## Stack markers

`package.json` with `react`; `next` for Next.js. Variants: function components with
hooks (teardown = the function returned from `useEffect`/`useLayoutEffect`) vs class
components (`componentWillUnmount`). React 18 StrictMode double-invokes effects in
development, which *exposes* missing cleanups (double listeners) - a useful test lever.

## Where the relevant code lives

`src/components/**`, `src/hooks/**` (`use*.ts` - custom hooks are where listeners and
timers usually live), `src/store/**` / `src/context/**` (module-level singletons),
`src/lib/socket.ts` / `signalr.ts`, `pages/` or `app/` (Next). Class components:
`componentDidMount` / `componentWillUnmount`.

## Dangerous / interesting APIs and patterns

- `useEffect(() => { ... })` that calls `addEventListener`, `setInterval`, `setTimeout`,
  `new ResizeObserver|IntersectionObserver|MutationObserver`, `subscribe(`, `socket.on(`,
  `connection.on(`, or a widget constructor, and has no `return () => ...` cleanup.
- Cleanup present but wrong: removes a *different* function reference than it added
  (inline arrow in both `add` and `remove`), or clears a timer id captured before it was set.
- `useEffect` with a missing dependency that re-runs and re-subscribes on every render
  (leak *and* duplicate handlers); `eslint-plugin-react-hooks` `exhaustive-deps` catches it.
- Widgets: `new Chart(`, `echarts.init(`, `L.map(`, `new mapboxgl.Map(`, `monaco.editor.create(`,
  `new Quill(`, `tinymce.init(`, `new Swiper(` in an effect without `destroy()`/`remove()`/`dispose()`
  in the cleanup; `useRef` holding the instance and never nulled.
- Subscriptions: RxJS `subscribe(` in an effect without `unsubscribe()` in cleanup; `store.subscribe(`
  (Redux/Zustand vanilla) return value discarded; `onAuthStateChanged(` (Firebase) unsubscribe discarded.
- `setState` after unmount inside async callbacks (React 18 no longer warns; the closure keeps the
  component reachable until the promise settles - Low unless the promise is long-lived).
- Module-level growth: `const cache = new Map()` / `[]` in a module written per render/route;
  `window.__x = ...`; event buses (`mitt`, `EventEmitter`) with `on` and no `off`.
- Context providers holding arrays of callbacks (`registerListener`) without an unregister path.
- Class components: `componentDidMount` acquisitions without `componentWillUnmount`.
- Next.js: `router.events.on('routeChangeStart', ...)` in `_app` or a page without `.off`.
- Third-party hooks used wrongly: `useQuery` with `refetchInterval` inside a component that
  remounts often is fine (library manages it); a hand-rolled polling `setInterval` is not.

## What "good" looks like

```tsx
export function SalesChart({ rows }: { rows: Row[] }) {
  const canvas = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const chart = new Chart(canvas.current!, config(rows));
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(canvas.current!.parentElement!);
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && chart.resetZoom();
    window.addEventListener('keydown', onKey);
    const id = setInterval(() => chart.update(), 30_000);
    return () => {                       // every acquisition above has a line here
      clearInterval(id);
      window.removeEventListener('keydown', onKey);
      ro.disconnect();
      chart.destroy();
    };
  }, [rows]);
  return <canvas ref={canvas} />;
}
```
Custom hook pattern: `useEventListener(target, type, handler)` and `useInterval(fn, ms)`
that own the cleanup, so components never call the raw APIs.

## Manual trace checklist

1. The most-visited routes (list <-> detail): open each component's effects and pair every
   acquisition from `leak_scan.py` with a line in the returned cleanup.
2. `src/hooks/**`: every custom hook that touches `window`, `document`, timers, sockets, or
   observers must return a cleanup; hooks are reused everywhere, so one missing cleanup is
   N leaks.
3. Module-level stores/contexts: arrays or Maps that grow with registrations, cached query
   results keyed by an unbounded id (search text, timestamps).
4. Socket/SignalR module: one connection per session; `on` handlers registered in components
   are removed with `off` in cleanup; reconnect does not create a second connection.
5. Widgets in effects: constructor + destroy pairing, and the instance not also stored in a
   module-level variable.
6. Class components (if any): `componentDidMount`/`componentWillUnmount` symmetry.

## Stack-specific false positives

- `fetch`/axios one-shot calls without cleanup: no leak (the promise settles); an
  `AbortController` in cleanup is a nicety, rate Info at most.
- `useEffect` with cleanup that only depends on `[]` and runs once: fine.
- Libraries that manage their own teardown when used via hooks: `react-chartjs-2`,
  `react-leaflet`, `@monaco-editor/react`, `@tanstack/react-query` polling,
  `react-use`'s `useEvent`/`useInterval`. Only raw constructor use needs pairing.
- StrictMode double effects in dev produce duplicate listeners *only if* cleanup is missing -
  that is the bug, not a false positive.
- Error boundaries (class components) rarely acquire resources; skip unless they do.

## Tooling

- React DevTools Profiler "Highlight updates" to see components re-rendering after
  navigation away (a symptom of live subscriptions).
- Chrome DevTools heap snapshot comparison (`heap-snapshot-procedure.md`); retainers to search:
  `FiberNode`, the component function name, `Chart`, `Map`, "Detached".
- `eslint-plugin-react-hooks` (`exhaustive-deps`) - missing deps cause re-subscription loops.
- `why-did-you-render` in development to catch effects re-running each render.

## References

- Effects and cleanup: https://react.dev/learn/synchronizing-with-effects#how-to-handle-the-effect-firing-twice-in-development
- You might not need an effect: https://react.dev/learn/you-might-not-need-an-effect
- CWE-401, CWE-772, CWE-400.
