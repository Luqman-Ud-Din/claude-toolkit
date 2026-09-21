# Vue reference for audit-technical-debt

Framework-idiom debt (Vue 2 global and instance API, filters, `.sync`, mixins beside
composables, Options/Composition mixing, Vue CLI) is detected by
`audit-frontend-best-practices` (FEBP); teardown leaks by `audit-frontend-memory-leak`
(FELEAK). This skill consumes those and adds end-of-life, hotspots, duplication, dead
components, TODO age, suppressions, maintenance-mode libraries and mixed library choices.

## Stack markers

`package.json` with `vue` (major 2 or 3), `nuxt`, `@vitejs/plugin-vue` or
`@vue/cli-service`; `*.vue` single-file components. Variants: Nuxt 2/3/4 (auto-imports
change dead-code rules), Quasar, Vue 2.7 "backport" projects mid-migration.

## Where the relevant code lives

- Hotspots: `views/` or `pages/` screens, large form components, `store/` (Vuex modules
  or Pinia stores), `composables/`, `mixins/`. `complexity.py` reads every `<script>` and
  `<script setup>` block of a `.vue` file; template complexity (`v-if` chains) is manual.
- Suppressions: `<!-- eslint-disable -->` in templates, `// eslint-disable vue/...`,
  `@ts-ignore` inside `<script lang="ts">`, `.eslintrc` rules set to `off`.
- Currency: `vue` major (Vue 2 ended 2023-12-31), `nuxt` major (Nuxt 2 ended
  2024-06-30), `vuex` (maintenance mode), `vue-router` major, `vuetify`/`element-ui`
  majors tied to Vue 2.

## Dangerous / interesting APIs and patterns

Mirrored in `scripts/patterns/vue.json` (only what FEBP does not already grep).
- **Removed in Vue 3 / maintenance-mode libraries**: event bus (`$on`, `$off`, `$once`,
  `new Vue()` as a bus), `slot-scope` and `slot=""`, `$listeners`, `$scopedSlots`,
  `.native`; `vuex` (Pinia is official), `vue-class-component` / `vue-property-decorator`,
  BootstrapVue 2, `element-ui` (Vue 2 only).
- **Inconsistent patterns**: Vuex + Pinia + hand-rolled `reactive()` stores; axios +
  `fetch` + Nuxt `useFetch`/`$fetch`; Vuetify + Element + PrimeVue; moment + date-fns.
- **Complexity shapes**: `methods` blocks with dozens of handlers, watchers that update
  other watched data, Vuex actions with nested API calls and commits, `computed`
  properties with branching business rules.
- **Dead code**: components never imported or used by tag, mixins no component lists,
  store modules never registered, routes pointing at removed views.

## What "good" looks like

Vue 3 with `<script setup lang="ts">`, Pinia stores, composables with tests, one HTTP
client wrapper, one UI library, eslint-plugin-vue `vue3-recommended` in CI, and scoped
suppressions:

```vue
<!-- eslint-disable-next-line vue/no-v-html -- sanitized by DOMPurify in useMarkdown() -->
```

## Manual trace checklist

1. Vue 2 still in use: list every Vue-2-only dependency (`npm ls vue`, UI kits, class
   components); that list sizes the migration, usually XL.
2. Top hotspot SFC: split template logic from business rules; decide which move to a
   composable or store with tests.
3. Dead-component candidates: search kebab-case and PascalCase tags, global
   `app.component(...)`, router `component: () => import(...)`, Nuxt auto-import folders.
4. Event-bus usages: map emitters to listeners; each pair is a migration step to props,
   emits or a store.
5. Mixed stores: which modules moved to Pinia; the remainder is next-quarter work.

## Stack-specific false positives

- Nuxt and `unplugin-vue-components` auto-import `components/` and `composables/`, so
  those files are never imported explicitly; `dead_code.py` treats them as entry points -
  confirm by tag search instead.
- Templates are not measured, so a simple-looking script can hide a complex template.
- `<!-- eslint-disable vue/multi-word-component-names -->` on page files is routine in Nuxt.

## Tooling

- `eslint-plugin-vue` with `vue/no-deprecated-*` rules:
  `npx eslint "src/**/*.{js,ts,vue}" --rule '{"complexity": ["warn", 15]}' -f json`.
- `npx vue-tsc --noEmit` (type debt in SFCs), `npx knip` (Vue and Nuxt plugins),
  `npx jscpd --min-lines 6 --reporters json src` (understands `.vue`).
- Migration sizing: the `@vue/compat` build logs every Vue 2 behaviour used at runtime
  (run in a branch or scratch copy); `npm outdated --json`.

## References

CWE-1121, CWE-1080, CWE-561, CWE-1041, CWE-477, CWE-1104, CWE-546. Vue 2 EOL:
https://v2.vuejs.org/lts/ ; migration guide: https://v3-migration.vuejs.org ; Nuxt
support: https://nuxt.com/docs/community/roadmap ; sibling skills:
`audit-frontend-best-practices`, `audit-frontend-memory-leak`.
