# Vue (and Nuxt) reference for audit-finding-writer

## Stack markers
`package.json` with `vue` (`nuxt` for Nuxt). Variants: Options API vs Composition API / `<script setup>`; Vue 2 vs 3.

## Where the relevant code lives
`src/`, `pages/`/`app/` (Nuxt), `composables/`, `stores/` (Pinia), `plugins/` (axios), `router/`, `.env*` (`VITE_*`/`NUXT_PUBLIC_*` are public), `nuxt.config.ts`.

## Remediation idioms
- XSS: mustache and `v-bind` escape; `v-html` only with `DOMPurify.sanitize()` and a comment; no `:href` from user input without scheme allow-list; no `eval`; avoid dynamic template compilation from user strings.
- Client auth: HttpOnly cookies (Nuxt `useCookie` server-side) preferred; bearer token in a Pinia store (memory) rather than `localStorage`; axios interceptor attaches `Authorization` only for `baseURL`; single in-flight refresh; logout resets stores (`$reset()`), storage, timers.
- Route guards: `router.beforeEach` / Nuxt `defineNuxtRouteMiddleware` are UX; server enforces.
- Secrets: `VITE_`/`NUXT_PUBLIC_` values ship to the browser; use Nuxt `runtimeConfig` private keys or an API route.
- Leaks: `onUnmounted`/`onBeforeUnmount` to remove listeners, clear intervals, disconnect observers, destroy widgets; `watch` stop handles; `useEventListener` from VueUse auto-cleans.
- Best practice: `"strict": true`, `<script setup lang="ts">`, `defineAsyncComponent` / lazy route `component: () => import()`, `vite build` with `sourcemap: false`, `eslint-plugin-vue` recommended rules, Pinia over ad-hoc global reactive state.
- a11y/i18n: semantic HTML, `aria-*`, focus trap in dialogs (`@vueuse/integrations/useFocusTrap`), `vue-i18n` for strings, `Intl.*` for dates/numbers, `dir` attribute driven by locale.
- Dates: parse ISO strings with offsets; `date-fns-tz`/`luxon`.

## Recurring references
CWE-79, CWE-922, CWE-200, CWE-401, CWE-601, ASVS 5.3.3, 8.2, 3.x, 14.4; OWASP A03, A05, A07; WCAG 2.2 AA.

## Stack-specific false positives
`v-html` on trusted, build-time content; `localStorage` for preferences; public runtime config values that are meant to be public.

## Tooling
`npm audit`, `npx eslint --ext .vue,.ts`, `npx @axe-core/cli`, `rollup-plugin-visualizer`, Vue DevTools, Chrome heap snapshots.
