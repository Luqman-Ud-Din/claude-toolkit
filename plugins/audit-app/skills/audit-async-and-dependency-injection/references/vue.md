# Vue (and Nuxt) reference for audit-async-and-dependency-injection

This skill is backend-focused. Vue's `provide`/`inject` is a lightweight DI
with the same shape as Angular's component providers (per component subtree)
and Nuxt's `useState`/plugins play the singleton role. Nuxt `server/**` is a
Node backend audited with `node-express.md`. The async half applies to the
client: unobserved rejections in `setup`/`onMounted`, missing cancellation,
fire-and-forget saves.

## Stack markers
`package.json` with `vue` or `nuxt`. Nuxt: `server/api/**`, `server/middleware/**`, `server/plugins/**`, `plugins/*.server.ts` (server-side, per request during SSR), `composables/`, `stores/` (Pinia).

## Where the relevant code lives
- Client: `composables/*.ts`, `stores/*.ts` (Pinia actions), components (`setup`, `onMounted`, `watch` with async callbacks), `plugins/*.ts` (`provide`), `app.vue`/layouts.
- Server (Nuxt): `server/api/**/*.ts`, `server/utils/*.ts` (clients), `server/plugins/*.ts`, `nuxt.config.ts` (`nitro`, `runtimeConfig`).

## Dangerous / interesting APIs and patterns
- DI-equivalent: Nuxt SSR - module-level state in composables/stores/plugins shared across requests on the server (`const state = ref()` at module scope in a composable instead of `useState('key')` - the classic cross-request leak; Nuxt docs call it out explicitly); Pinia stores created outside `setup` on the server; `provide()` of a per-user object from a plugin that runs once per server instance; `server/utils` singletons capturing `event`/request data; `useRequestHeaders`/`useRequestEvent` values stored in module variables.
- VOID: `onMounted(async () => ...)` with no try/catch (rejection unhandled - Vue `app.config.errorHandler` catches sync errors and awaited lifecycle promises in Vue 3, but not nested unawaited promises); `watch(src, async () => ...)` without error handling; Pinia actions that are `async` and called without `await`/`.catch` from components; `useFetch` errors ignored (`error` ref never read).
- CANCEL: `fetch`/`$fetch` without `signal`; `watch`-driven refetch without cancelling the previous (stale response race - use `useFetch` with `watch` or an `AbortController` per call); `onUnmounted` not aborting in-flight requests; `useAsyncData` without `dedupe`/`key` (duplicate concurrent fetches).
- FIRE: `store.save(dto)` unawaited in a submit handler; `navigateTo()` after an unawaited save; `$fetch('/api/audit', { method: 'POST' })` fire-and-forget for critical writes.
- BLOCK: heavy sync work in `setup`/`computed` (INP - hand to performance); server: sync fs/crypto in `server/api` handlers (node-express BLOCK).
- TIMEOUT: `$fetch`/`useFetch` without `timeout` (ofetch supports `timeout`); server-side `$fetch` to upstreams without timeout or retry config (`retry`, `retryDelay`).

## What "good" looks like
```ts
// Nuxt: per-request state on the server, never module-level
export const useTenant = () => useState<string | null>('tenant', () => null);

// composable: cancellable, errors observed
const { data, error, refresh } = await useFetch('/api/orders', { query: { page }, watch: [page], timeout: 5000, retry: 1 });
watchEffect(() => { if (error.value) toast.error(error.value.message); });

// submit: awaited, failure shown
async function onSubmit() { try { await store.save(form); await navigateTo('/orders'); } catch (e) { toast.error(String(e)); } }

// manual fetch with abort on unmount
const ac = new AbortController(); onUnmounted(() => ac.abort());
const res = await $fetch('/api/report', { signal: ac.signal, timeout: 10_000 });

// server/utils/http.ts - one client, timeouts
export const pricing = $fetch.create({ baseURL: process.env.PRICING_URL, timeout: 3000, retry: 2 });
```

## Manual trace checklist
1. Nuxt SSR: grep composables/stores/plugins for module-level `ref`/`reactive`/`let` holding user or tenant data - cross-request leak on the server.
2. Server code (`server/**`): run `node-express.md` checks - clients per request, timeouts, unawaited promises, module state.
3. `onMounted`/`watch` async callbacks: try/catch or `error` ref handled?
4. Submit/pay/save handlers: awaited with error handling?
5. `$fetch`/`useFetch`: `timeout`, `signal`, `key`/`dedupe` set where refetches race?

## Stack-specific false positives
- Module-level `ref` in a composable used only on the client (`ssr: false` app) - fine, note the constraint.
- `void $fetch('/api/telemetry')` for non-critical telemetry with `onResponseError` handling.

## Tooling
ESLint `vue/no-async-in-computed-properties`, `@typescript-eslint/no-floating-promises`, `@typescript-eslint/no-misused-promises`; Nuxt DevTools (Server routes, Payload - shows shared state), `nuxi analyze`; `app.config.errorHandler` + `vueApp.config.errorHandler` in a plugin to log unhandled errors in staging.

## Hand-off
Client leaks: `audit-frontend-memory-leak`. Render/INP cost: `audit-performance-and-scalability`, `audit-frontend-best-practices`.

## References
CWE-390, CWE-248, CWE-1088, CWE-362; Nuxt docs "State management - useState (SSR-safe shared state)", "Data fetching - useFetch options (timeout, retry, dedupe)", "Server - utils and plugins"; Vue docs "Provide / Inject", "Error handling (app.config.errorHandler)"; ofetch README (`timeout`, `retry`, `signal`).
