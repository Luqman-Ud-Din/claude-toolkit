# Vue reference for audit-frontend-memory-leak

## Stack markers

`package.json` with `vue` (3.x assumed; Vue 2 uses `beforeDestroy`/`destroyed` instead of
`onBeforeUnmount`/`onUnmounted`); `nuxt` for Nuxt. Variants: `<script setup>` /
Composition API (teardown = `onUnmounted`, `onBeforeUnmount`, `onScopeDispose`, or the stop
handle returned by `watch`/`watchEffect`) vs Options API (`beforeUnmount`/`unmounted`).
`<KeepAlive>` changes the rules: cached components fire `onDeactivated`, not `onUnmounted`.

## Where the relevant code lives

`src/components/**/*.vue`, `src/views/**`, `src/composables/use*.ts` (listeners and timers
live here), `src/stores/**` (Pinia - session-long singletons), `src/plugins/socket.ts`,
Nuxt `plugins/`, `composables/`, `app.vue`.

## Dangerous / interesting APIs and patterns

- `onMounted(() => { ... })` that calls `addEventListener`, `setInterval`, `setTimeout`,
  `new ResizeObserver|IntersectionObserver|MutationObserver`, `subscribe(`, `socket.on(`,
  or a widget constructor, with no matching `onUnmounted`/`onBeforeUnmount` in the same
  script (or `onScopeDispose` in a composable).
- Options API: `mounted()` acquisitions without `beforeUnmount()`/`unmounted()` (Vue 2:
  `beforeDestroy`/`destroyed`).
- `watch(` / `watchEffect(` created *outside* setup (in a callback, in `onMounted`, in a
  store action) - those are not auto-stopped; the returned stop handle must be called.
- `watch(source, cb, { deep: true })` on a large reactive object: not a leak but a growth
  multiplier; note it in Impact if the object grows.
- Widgets: `new Chart(`, `echarts.init(`, `L.map(`, `new mapboxgl.Map(`, `monaco.editor.create(`,
  `new Quill(`, `tinymce.init(`, `new Swiper(` without `destroy()`/`remove()`/`dispose()`;
  instance stored in a `ref` and never nulled; `markRaw` missing (Vue proxies the whole widget,
  which is slow and keeps it reachable).
- Subscriptions: RxJS `subscribe(` (VueUse `useObservable` is the safe form), `store.$subscribe(`
  and `store.$onAction(` return an unsubscribe that is discarded (they auto-stop only when
  called inside a component setup - not in a plain module).
- Global growth: `app.config.globalProperties.$x`, module-level `const cache = new Map()`,
  Pinia state arrays appended per navigation (`history.push(...)`, `notifications.push(...)`)
  without a cap; `provide()`d registries with `register` and no `unregister`.
- Event bus: `mitt()` / `emitter.on(` without `emitter.off(` in unmount.
- `<KeepAlive>` components that start timers in `onActivated` and do not stop them in
  `onDeactivated`.
- Nuxt: `useFetch`/`useAsyncData` polling via `setInterval` in a page without `onUnmounted`;
  `router.beforeEach` registered in a component (returns an unregister function - usually discarded).

## What "good" looks like

```vue
<script setup lang="ts">
import { onMounted, onUnmounted, ref, markRaw, watch } from 'vue';
const canvas = ref<HTMLCanvasElement>();
let chart: Chart | undefined;
let ro: ResizeObserver | undefined;
let timer: number | undefined;
const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') chart?.resetZoom(); };

onMounted(() => {
  chart = markRaw(new Chart(canvas.value!, config()));
  ro = new ResizeObserver(() => chart?.resize()); ro.observe(canvas.value!.parentElement!);
  window.addEventListener('keydown', onKey);
  timer = window.setInterval(() => chart?.update(), 30_000);
});
onUnmounted(() => {                          // one line per acquisition above
  clearInterval(timer);
  window.removeEventListener('keydown', onKey);
  ro?.disconnect();
  chart?.destroy();
});
const stop = watch(() => props.rows, r => chart?.update(), { deep: false }); // auto-stopped in setup
</script>
```
Composable form: `useEventListener(window, 'keydown', onKey)` and `useIntervalFn` from VueUse
own their teardown via `onScopeDispose`.

## Manual trace checklist

1. The most-visited views (list <-> detail): pair every acquisition from `leak_scan.py` with a
   line in `onUnmounted`/`onBeforeUnmount`/`beforeUnmount`.
2. `composables/`: every composable that touches `window`, timers, sockets, observers, or
   creates watchers outside setup must clean up via `onScopeDispose`/`onUnmounted`.
3. Pinia stores: arrays/Maps that grow per navigation or per socket message without a cap or
   removal; `$subscribe`/`$onAction` handles discarded in modules.
4. Socket plugin: one connection per session; component-level `socket.on` paired with
   `socket.off` in unmount; reconnect does not stack connections.
5. `<KeepAlive>` users: `onActivated`/`onDeactivated` symmetry.
6. Widgets: constructor/destroy pairing and `markRaw` on the instance.

## Stack-specific false positives

- `watch`/`watchEffect`/`computed` created synchronously inside `setup`/`<script setup>`:
  auto-stopped on unmount.
- `store.$subscribe` called inside a component setup: auto-detached on unmount (unless
  `{ detached: true }`).
- VueUse helpers (`useEventListener`, `useIntervalFn`, `useResizeObserver`, `useWebSocket`):
  own their teardown.
- Vue Router `onBeforeRouteLeave`/`onBeforeRouteUpdate` inside setup: auto-removed.
- `fetch`/axios one-shot calls: no leak; abort on unmount is a nicety.
- `<Teleport>`/`<Transition>` do not leak by themselves.

## Tooling

- Vue DevTools > Components: after navigating away, a component still listed means it is
  retained (KeepAlive aside).
- Chrome DevTools heap snapshot comparison (`heap-snapshot-procedure.md`); retainers to search:
  `ComponentInternalInstance`, `ReactiveEffect`, the component name, `Chart`, `Map`, "Detached".
- `eslint-plugin-vue` has no cleanup rule; recommend VueUse helpers in remediation so the
  problem disappears structurally.

## References

- Lifecycle hooks: https://vuejs.org/api/composition-api-lifecycle.html
- `onScopeDispose` and effect scopes: https://vuejs.org/api/reactivity-advanced.html#onscopedispose
- VueUse: https://vueuse.org
- CWE-401, CWE-772, CWE-400.
