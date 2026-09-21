# Vue (and Nuxt) reference for audit-performance-and-scalability

Scope here is runtime behaviour: render-blocking resources, API calls per page
and duplicates, client caching, images, re-renders, Core Web Vitals. Bundle,
code splitting and lint hygiene are `audit-frontend-best-practices`. For Nuxt,
`server/**` is a Node backend - apply `node-express.md` to it.

## Stack markers
`package.json` with `vue` (Vite SPA) or `nuxt` (SSR/SSG, Nitro server). Data layer: `useFetch`/`useAsyncData` (Nuxt, deduped by key), `@tanstack/vue-query`, Pinia stores, or bare `fetch`/axios in `onMounted` (no caching, no dedup).

## Where the relevant code lives
`index.html`/`nuxt.config.ts` `app.head` (blocking scripts, fonts, preconnect), `nuxt.config.ts` (`routeRules` cache/prerender, `image`, `nitro.compressPublicAssets`), `plugins/` (global fetch setup), `stores/*.ts` (Pinia - cache lifetime), page/layout components (`onMounted` fan-out, `useFetch` keys), `components/` (large lists, inline handlers), `public/`/`assets/` images.

## Dangerous / interesting APIs and patterns
- RENDER-BLOCK: `<script src>` in head without `defer`/`async` (`app.head.script` without `defer: true`/`tagPosition: 'bodyClose'`); third-party CSS/fonts without `preconnect`; `@nuxtjs/google-fonts`/`@nuxt/fonts` not used; SPA mode (`ssr: false`) for a public landing page.
- CALLS-PER-PAGE: several components on one page each calling `useFetch('/api/products')` without a shared `key` or each calling a store action that fetches unconditionally; `onMounted(() => axios.get(...))` in sibling components; layout + page both fetching the same data; `watch` on a query param refetching without debounce; polling with `setInterval` at high frequency.
- CLIENT-CACHE: reference data refetched on every route; Pinia store actions that never check "already loaded"; `useFetch` with `key` omitted and dynamic URLs (cache miss every time); no `routeRules` `swr`/`isr`/`cache` for cacheable pages; bare axios with no cache; API `Cache-Control` absent (cross-check backend).
- RERENDER: `v-for` without `:key` (or index keys on reorderable lists); expensive `computed` replaced by methods in templates (`{{ total() }}` recomputes every render); deep `watch` on large objects; reactive wrapping of huge arrays (`ref(bigList)` -> use `shallowRef`/`markRaw`); large tables without virtual scroll (`vue-virtual-scroller`, Vuetify `v-virtual-scroll`); `v-if`/`v-show` misuse on heavy subtrees; global store mutations triggering every subscriber.
- IMAGE: `<img>` instead of `<NuxtImg>`/`<NuxtPicture>` (or no `width`/`height`, no `loading="lazy"`, no WebP/AVIF), hero without `preload`/`fetchpriority="high"`, base64 images in JSON.
- CWV: LCP image not preloaded; CLS from images without dimensions and late-hydrated components; INP from heavy sync click handlers; hydration cost of large SSR pages (`<LazyComponent>`/`hydrate-on-visible` in Vue 3.5).

## What "good" looks like
```ts
// Nuxt: deduped by key across components, cached in payload
const { data: products } = await useFetch('/api/products', { key: `products-${page.value}`, query: { page } });
// Pinia: fetch once
const useUnits = defineStore('units', { state: () => ({ items: [] as Unit[], loaded: false }),
  actions: { async load() { if (this.loaded) return; this.items = await $fetch('/api/units'); this.loaded = true; } } });
const list = shallowRef<Row[]>([]);                      // no deep reactivity on 10k rows
const total = computed(() => rows.value.reduce(...));    // not a method in the template
```
```vue
<NuxtImg src="/hero.jpg" width="1200" height="600" format="webp" preload fetchpriority="high" />
<img :src="p.thumb" width="80" height="80" loading="lazy">
<tr v-for="row in rows" :key="row.id">
```
`nuxt.config.ts`: `routeRules: { '/': { prerender: true }, '/products/**': { swr: 300 } }`, `nitro: { compressPublicAssets: true }`, `app.head.link: [{ rel: 'preconnect', href: 'https://api.example.com' }]`.

## Manual trace checklist
1. Landing page: enumerate fetches on setup/mount across layout + page + components; duplicates by URL/key.
2. Pinia stores: "already loaded" guards for reference data.
3. Head config: blocking scripts, fonts, preconnect.
4. Largest list: `:key`, virtual scroll, `shallowRef`, computed vs methods.
5. Images: `NuxtImg`/dimensions/lazy/format; LCP preload.
6. Lighthouse desktop + mobile on landing + dashboard if a URL exists; record LCP/INP/CLS.

## Stack-specific false positives
- Same `useFetch` key in several components - Nuxt dedupes; not a duplicate.
- `<img>` for icons/SVGs.
- `ssr: false` for an authenticated-only admin app - acceptable; note LCP impact.

## Tooling
Vue DevTools (component render timings, Pinia state), `npx lighthouse`, `nuxi analyze` (bundle - delegated), Nuxt DevTools "Server routes"/"Payload" panels, Chrome DevTools Performance (Interactions for INP), `web-vitals` library, `@nuxtjs/web-vitals`.

## References
web.dev "Core Web Vitals"; Vue docs "Performance" (shallowRef, v-memo, virtualization); Nuxt docs "Data fetching", "Route rules / hybrid rendering", "Nuxt Image", "Fonts".
