# Vue (2 and 3, Nuxt) reference for audit-frontend-xss-and-dom-safety

## Stack markers
`package.json` with `vue`, `nuxt`, `@vue/cli-service`, `vite` + `@vitejs/plugin-vue`. Variants: Options API vs Composition API (same sinks), Vue 2 (`Vue.compile`, filters) vs Vue 3, Nuxt SSR (server-rendered HTML with `useHead` inline scripts), Quasar/Vuetify component `html` props.

## Where the relevant code lives
`src/**/*.vue` (templates: `v-html`, `:href`, `:src`, `:srcdoc`), `<script>` blocks and `composables/**` (`innerHTML`, `eval`), `render()` functions / JSX (`domProps: { innerHTML }` in Vue 2, `innerHTML:` prop in Vue 3 `h()`), `public/index.html` / `nuxt.config.ts` `app.head.script` (third-party scripts, inline), `plugins/**` (global filters/directives writing DOM), markdown wrappers (`vue-markdown`, `markdown-it` with `html: true`), editors (`vue-quill`, `tiptap` HTML export).

## Dangerous / interesting APIs and patterns
- Bypasses (BYPASS): `v-html="x"` (no sanitization at all), `v-bind:innerHTML` / `:inner-html`, render function `h('div', { innerHTML: x })`, Vue 2 `domProps: { innerHTML: x }`, `{{{ }}}` triple mustache (Vue 1 - obsolete but appears in migrated code), Vuetify/Quasar `html` props (`v-tooltip` `html`, `q-tooltip`), `useHead({ script: [{ innerHTML: x }] })` in Nuxt.
- Raw HTML (HTML): `.innerHTML =`, `.outerHTML =`, `insertAdjacentHTML(`, `document.write(`, jQuery `.html(`.
- Element access (DOM): `this.$refs.x.innerHTML`, `ref.value.innerHTML`, `this.$el.innerHTML`, custom directives `el.innerHTML = binding.value` (a `v-highlight` directive is the classic), `document.querySelector(...).innerHTML`.
- URLs (URL): `:href="user"` - **Vue does not block `javascript:`**; `:src` on `<iframe>`/`<object>`/`<embed>`, `:srcdoc`, `:formaction`, `:xlink:href`, `window.open(user)`, `location.href = user`, `router.push(user)` / `navigateTo(user)` external (open redirect), `<a :href>` inside `v-for` over API data.
- Dynamic attributes: `v-bind="obj"` where `obj` comes from JSON can inject `innerHTML` (Vue 3 treats `innerHTML` key as a DOM prop) - report as HTML class.
- Code (EVAL): `eval(`, `new Function(`, `setTimeout("..."`, `Vue.compile(userTemplate)` / `compile()` from `vue` on runtime strings, `<component :is>` with a template string, `template:` option built from user data (runtime compiler build), Nuxt `useHead` `script` with user strings.
- SRI/INLINE: `public/index.html` `<script src="https://...">` without `integrity`; `nuxt.config.ts` `app.head.script: [{ src: 'https://...' }]` (supports `integrity`, `crossorigin`); inline `innerHTML` scripts for GTM; `vite` `build.modulePreload` not relevant.

## What "good" looks like
```vue
<!-- Default interpolation is escaped: no v-html for text -->
<p>{{ comment.body }}</p>

<!-- Rich text: sanitize the same value, state why -->
<script setup lang="ts">
import DOMPurify from 'dompurify';
// Justified v-html: CMS articles need tables; DOMPurify with fixed allow-list.
const safeHtml = computed(() => DOMPurify.sanitize(props.article.html, { ALLOWED_TAGS: ['p','b','i','a','table','tr','td'], ALLOWED_ATTR: ['href'] }));
const safeHref = computed(() => { try { const u = new URL(props.link, location.origin); return ['http:','https:'].includes(u.protocol) ? u.href : '#'; } catch { return '#'; } });
</script>
<template>
  <div v-html="safeHtml"></div>
  <a :href="safeHref">{{ props.label }}</a>
</template>
```
```ts
// nuxt.config.ts third-party script with SRI
app: { head: { script: [{ src: 'https://cdn.example.com/lib.js', integrity: 'sha384-...', crossorigin: 'anonymous' }] } }
```

## Manual trace checklist
1. Every `v-html` and render-function `innerHTML`: source of the bound value, sanitizer in the computed/prop chain, and who can edit the source.
2. Markdown renderers: `markdown-it` `html: true`, `linkify`, and whether output passes through DOMPurify.
3. `:href`/`:src`/`:srcdoc` bound to API or route data - Vue does not filter schemes, so every one needs a check.
4. Custom directives and `$refs` writes; `v-highlight`/`v-tooltip` style helpers.
5. `v-bind="$attrs"`/`v-bind="config"` from JSON configuration.
6. `public/index.html` and `nuxt.config.ts` head scripts: SRI and inline snippets; Nuxt `useHead` calls with dynamic `innerHTML`.
7. Nuxt SSR: `useState`/payload embedding is escaped by devalue; custom `<script>` tags in `app.vue` with `JSON.stringify` are not (`</script>` breakout).

## Stack-specific false positives
- `v-html="icon"` where `icon` is an imported constant SVG string - justified, Info.
- `v-html` on i18n strings from files only developers edit (`vue-i18n` `v-html` for formatted messages) - Info, but note that runtime-editable translations change the answer.
- `:href="`/items/${item.id}`"` relative paths; `:href="`mailto:${email}`"` with validated email.
- `$refs.input.focus()`, `.value`, `.textContent`.
- `eval`/`new Function` in tests or Vite/webpack shims.

## Tooling
- `npx eslint --plugin vue` with `vue/no-v-html`, `vue/no-v-text-v-html-on-component`; `eslint-plugin-no-unsanitized`.
- `semgrep --config p/vue` (`vue-v-html`, `vue-href-javascript`), `--config p/javascript`.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/vue.json`; `scan_html_scripts.py` for `public/index.html` and `.vue` templates.

## References
Vue Security guide ("Injecting HTML", "Injecting URLs"); Nuxt `useHead` docs; OWASP DOM based XSS Prevention Cheat Sheet; OWASP SRI. CWE-79, CWE-95, CWE-601, CWE-829; ASVS 5.3.3, 5.3.10, 14.2.3, 14.4.3; OWASP A03:2021, A05:2021, A08:2021.
