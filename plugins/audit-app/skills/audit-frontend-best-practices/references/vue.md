# Vue reference for audit-frontend-best-practices

## Stack markers

`package.json` with `vue`; `nuxt` marks Nuxt. Vue 2 (`vue@2`, `vue-template-compiler`,
`@vue/cli-service`) vs Vue 3 (`vue@3`, `@vitejs/plugin-vue`). Vue 2 reached end
of life in Dec 2023 - a Vue 2 app is an automatic Fail for "Component model"
with a High finding (CWE-1104), regardless of code quality. Variants: Options API
vs Composition API vs `<script setup>`; Vuex vs Pinia; Vue CLI (webpack) vs Vite.

## Where the relevant code lives

- `tsconfig.json`: `strict`, plus `vueCompilerOptions.strictTemplates` (Volar/vue-tsc).
  JS-only SFCs (`<script>` without `lang="ts"`) count as no type checking.
- `vite.config.*`: `build.sourcemap`, `build.minify`, `build.chunkSizeWarningLimit`,
  `build.rollupOptions.output.manualChunks`.
- `vue.config.js` (Vue CLI): `productionSourceMap`, `configureWebpack.performance.hints`,
  `chainWebpack` budgets.
- `nuxt.config.*`: `sourcemap: { client: false }`, `vite.build.*`, `experimental.*`,
  `routeRules`; Nuxt `pages/` is code-split per page automatically.
- Routes: `router/index.ts` (`createRouter`), route records with `component: () => import()`.
- Components: `*.vue` SFCs; `defineComponent`, `<script setup>`.
- Lint: `eslint-plugin-vue` with `plugin:vue/vue3-recommended`; `vue-tsc --noEmit`.

## Dangerous / interesting APIs and patterns

- Vue 2 residue: `new Vue(`, `Vue.extend(`, `Vue.component(`, `Vue.use(`, `Vue.prototype.$x =`,
  `this.$set(`, `this.$delete(`, `filters:`, `$listeners`, `$scopedSlots`, `.sync` modifier,
  `v-on:hook:`, `@vue/composition-api` shim.
- Mixed models: `mixins: [` next to `<script setup>` elsewhere; `data() {` + `setup()` in the
  same component; Vuex `mapState` and Pinia `storeToRefs` coexisting.
- Type discipline: `: any`, `as any`, `defineProps<any>`, props declared without types
  (`props: ['a', 'b']`).
- Rendering cost: `v-for` without `:key`, `:key="index"` on mutable lists, `v-if` and `v-for`
  on the same element (Vue 3 changed precedence; a compile warning), heavy computed work in
  methods instead of `computed()`, `watch` with `deep: true` on large objects,
  no `shallowRef` for big immutable payloads.
- Routes: `component: SomeView` (static import) for feature routes; missing
  `defineAsyncComponent` for heavy in-page widgets.
- Build: `sourcemap: true` (Vite), `productionSourceMap: true` (Vue CLI), `minify: false`,
  Nuxt `sourcemap.client: true`.
- Bundle-hostile imports: `import _ from 'lodash'`, `import moment from 'moment'`,
  `import ElementPlus from 'element-plus'` (whole library) without `unplugin-vue-components`.
- Deprecated: `Vue.config.productionTip`, `@vue/cli-service` (maintenance mode), `vue-class-component`.

## What "good" looks like

```ts
// router/index.ts
export const router = createRouter({ history: createWebHistory(), routes: [
  { path: '/', component: () => import('@/views/HomeView.vue') },
  { path: '/reports', component: () => import('@/views/ReportsView.vue') },
]});
```
```vue
<script setup lang="ts">
import { computed } from 'vue';
const props = defineProps<{ rows: Product[] }>();
const sorted = computed(() => [...props.rows].sort(byName));
</script>
<template>
  <ProductRow v-for="r in sorted" :key="r.id" :row="r" />
</template>
```
```ts
// vite.config.ts
export default defineConfig({ plugins: [vue()], build: { sourcemap: false, chunkSizeWarningLimit: 500 } });
// nuxt.config.ts
export default defineNuxtConfig({ sourcemap: { server: true, client: false } });
```

## Manual trace checklist

1. `main.ts` / `app.vue` / Nuxt `app.vue`: static imports of feature views land in the entry
   chunk. Compare with `route_scan.py`.
2. The build script CI runs: `vite build --mode`, `vue-cli-service build`, `nuxt build`;
   check the mode-specific config branch for sourcemaps.
3. Largest list/table view: `:key` stability, `computed` vs method calls in template,
   `v-memo` or virtualization for >200 rows.
4. Count SFCs by style: `<script setup>` / `defineComponent` + `setup()` / Options API.
   Report the ratio; Options API on Vue 3 is supported but mixing with Composition in one
   component is a Partial.
5. Vue 2 apps: check for `@vue/compat` (migration build) and a written migration plan; that
   turns the Fail into a Partial.

## Stack-specific false positives

- `defineComponent` with Options API is valid Vue 3 - a style choice, not legacy. Only flag
  mixing inside one component or Vue-2-only APIs.
- `:key="index"` on static lists (menus, tabs) is fine.
- Nuxt `pages/` routes are lazy by construction; `route_scan.py` marks them lazy by convention.
- `sourcemap: 'hidden'` is fine if maps are uploaded to an error tracker and not deployed.
- Global component registration of a handful of base components (`BaseButton`) is normal;
  only whole-UI-library registration is a bundle finding.

## Tooling

- `npx vue-tsc --noEmit --strict` to count strict-mode errors.
- `npx vite build` + `rollup-plugin-visualizer` (`stats.html`), or `npx nuxi analyze`.
- `npx eslint --ext .vue,.ts src` with `eslint-plugin-vue` (rule `vue/no-deprecated-*` set
  flags Vue 2 residue automatically; if the plugin is absent, that is the "Lint config" finding).
- `npx @vue/compat` migration build reports deprecations at runtime during manual testing.

## References

- Vue 3 migration guide (breaking changes list): https://v3-migration.vuejs.org/breaking-changes/
- Vue style guide: https://vuejs.org/style-guide/
- Nuxt sourcemap config: https://nuxt.com/docs/api/nuxt-config#sourcemap
- CWE-1104 (Vue 2 EOL), CWE-540 (source maps), ASVS-14.2.1, ASVS-14.3.2.
