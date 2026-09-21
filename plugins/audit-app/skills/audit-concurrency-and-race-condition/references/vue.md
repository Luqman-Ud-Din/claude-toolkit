# Vue (and Nuxt) reference for audit-concurrency-and-race-condition

## Stack markers
`package.json` with `vue` or `nuxt`. Variants: Vue 2/3; Pinia/Vuex; `useFetch`/`$fetch` (ofetch has `retry` defaults: 1 for GET/PUT/DELETE-safe methods, 0 for POST unless configured); Nuxt `server/api/**` (Nitro) is backend code: audit with `node-express.md`, including module-level state in server route files (shared across requests in one instance).

## Where the relevant code lives
- Client: component `@submit`/`@click` handlers, Pinia actions that call the API, `services/api.ts` (`$fetch.create({ retry })`, axios interceptors), optimistic store updates, offline queues (PWA/workbox background sync).
- Server (Nuxt): `server/api/**`, `server/utils/**`, `server/plugins/**` (cron via `nitro` tasks or `node-cron` started once per instance).

## Dangerous / interesting APIs and patterns
- Submit handlers without an in-flight guard: `@click="pay()"` and no `:disabled="submitting"`; `@submit` on the form plus `@click` on the button.
- `$fetch(url, { method: 'POST', retry: 3 })` or a global `$fetch.create({ retry })` applied to mutations; `useFetch` with `immediate` re-running a POST on reactive dependency change; `watch` on form state triggering a save on every keystroke without debounce or a key.
- Pinia actions awaiting a mutation while the UI allows a second dispatch; `Promise.all` on dependent mutations.
- Optimistic store mutation before the server confirms (`state.balance -= amount`) without rollback on error or refetch on settle.
- Stale edits: form initialised from a cached store object, PUT sends the whole stale object; no version/ETag; server last-write-wins.
- `<ClientOnly>`/SSR double execution: a mutation in `setup()` runs on server and client; `onMounted` mutation re-running under HMR.
- Nuxt server routes: module-level `const cache = new Map()`; `node-cron` started in a plugin on every instance.
- Multiple tabs sharing `localStorage` (Pinia persisted state) both checking out.

## What "good" looks like
```ts
const submitting = ref(false);
let key = crypto.randomUUID();                          // one intent, one key
async function pay() {
  if (submitting.value) return;
  submitting.value = true;
  try { await api.post('/orders/pay', body, { headers: { 'Idempotency-Key': key } }); key = crypto.randomUUID(); }
  finally { submitting.value = false; }
}
// $fetch: retries only for safe methods
const api = $fetch.create({ retry: 0, onRequest({ options }) { if (options.method === 'GET') options.retry = 2; } });
// edits: version on PUT, 409 -> reload
await api.put(url, { ...dto, version }, { headers: { 'If-Match': etag } });
```
`:disabled="submitting"` on the button; a client key on mutations the server treats as idempotent; 409 handling that reloads.

## Manual trace checklist
1. For each money/stock/uniqueness mutation the backend audit flagged: client trigger, in-flight guard, client key, retry config.
2. `grep -rn "retry" src | grep -i "\$fetch\|useFetch\|axios"`.
3. `grep -rn "watch(\|watchEffect(\|onMounted(" src | grep -i "post\|save\|submit\|pay"`: mutations fired reactively.
4. Optimistic store updates: rollback and refetch present.
5. Edit forms: version/ETag on PUT; 409 handling.
6. Nuxt server routes/plugins: apply `node-express.md` (module-level state, check-then-act, keys, cron per instance).

## Stack-specific false positives
- `retry` on GET only; ofetch default retry on POST is 0 (confirm no global override).
- Debounced autosave on drafts (no money/stock effect).
- Optimistic UI with rollback and refetch.
- `:disabled="submitting"` alone is UX; record as "client mitigation present", not as closing the server finding.

## Tooling
`grep -rn ":disabled" src --include=*.vue | grep -i "submit\|pay\|save"`; Vue DevTools (Pinia timeline) to see duplicate actions; Network tab throttling to reproduce; `scripts/double_submit.sh` against the API with the client's exact payload.

## References
CWE-362, ASVS 11.1.4; ofetch retry options; Nuxt server routes and Nitro tasks; Stripe idempotent requests. The backend reference owns the server-side finding.
