# Vue reference for audit-accessibility-and-i18n

## Stack markers

`package.json` with `vue` (3.x assumed); `nuxt` adds `@nuxtjs/i18n` and `useHead` titles.
i18n: `vue-i18n` (`$t`, `t()`, `<i18n-t>`, `$n`, `$d`, `useI18n`), `@nuxtjs/i18n`
(`useLocalePath`, `setLocale`). UI kits: Vuetify, PrimeVue, Element Plus, Quasar, Naive UI
(dialogs/labels mostly built in), Headless UI for Vue, Radix Vue.

## Where the relevant code lives

`src/components/**/*.vue`, `src/views/**`, `App.vue` (skip link, `<main>`), `index.html`
(`<html lang dir>`), `src/router/index.ts` (`meta.title`, `afterEach` focus/title),
`src/i18n.ts` + `src/locales/*.json`, `src/assets/*.css` (focus, logical props),
`src/utils/format.ts`.

## Dangerous / interesting APIs and patterns

- `<input placeholder>` without `<label for>`, `aria-label`, `:aria-label`; Vuetify
  `<v-text-field>` without `label`; Element Plus `<el-input>` outside `<el-form-item label>`.
- `<img :src>` without `alt`/`:alt`; icon components in buttons without text/`aria-label`.
- Custom modals: `<div v-if="open" class="modal">` without `role="dialog"`, `aria-modal`,
  `aria-labelledby`, a focus trap (`focus-trap-vue`, `@vueuse/integrations/useFocusTrap`,
  `v-focus-trap`), or focus restore; `<Teleport to="body">` modals are the usual offenders.
- `@click` on `<div>`/`<span>`/`<li>` without `role="button"`, `tabindex="0"`, `@keydown.enter`/
  `@keydown.space`; `<a>` without `href`.
- `tabindex` greater than 0; `autofocus` outside dialogs.
- Route changes: no `document.title` update (`router.afterEach` / `useHead`) and no focus
  management; skip link missing.
- `v-html` content with no structure (also XSS skill).
- Colour-only status; `outline: none` in global CSS without `:focus-visible`.
- i18n: text nodes and attribute strings not wrapped in `$t()`/`t()`/`<i18n-t>`; strings in
  composables/stores (`ElMessage.success('Saved')`, validation messages).
- Formatting: `toLocaleDateString()` without a locale; `.toFixed(2)`, `'$' + price`,
  `dayjs().format('DD/MM/YYYY')`; `$d`/`$n` unused while `Intl.*('en-US')` hard-coded.
- Plurals: `` `${n} item${n === 1 ? '' : 's'}` ``; `$tc` with only two forms for locales that
  need more; `$t` with `{count}` interpolation instead of `plural` (`|`-separated forms).
- RTL: `margin-left`, `padding-right`, `text-align: left`, `left: 0`, `float: left` instead of
  logical properties; `dir="ltr"` hard-coded; icons with direction not mirrored; `dir` not set
  from `locale` on `<html>`.
- Text expansion: fixed `width` on buttons/labels, `white-space: nowrap; overflow: hidden` on
  translatable text, fixed-height cards.

## What "good" looks like

```vue
<script setup lang="ts">
import { useI18n } from 'vue-i18n';
const { t, n, d, locale } = useI18n();
</script>
<template>
  <a class="skip-link" href="#main">{{ t('skip') }}</a>
  <main id="main" tabindex="-1">
    <h1>{{ t('checkout.title') }}</h1>
    <label for="email">{{ t('checkout.email') }}</label>
    <input id="email" type="email" autocomplete="email" v-model="email"
           :aria-invalid="!!errors.email" :aria-describedby="errors.email ? 'email-err' : undefined">
    <p v-if="errors.email" id="email-err" role="alert">{{ t('checkout.emailInvalid') }}</p>
    <img :src="product.image" :alt="product.name">
    <button type="button" :aria-label="t('cart.remove', { name: item.name })"><TrashIcon aria-hidden="true" /></button>
    <p>{{ n(total, 'currency') }} - {{ d(today, 'short') }}</p>
    <p>{{ t('cart.items', count) }}</p>   <!-- "no items | one item | {count} items" -->
  </main>
  <Teleport to="body">
    <div v-if="confirmOpen" ref="dialogEl" role="dialog" aria-modal="true" aria-labelledby="confirm-title">
      <h2 id="confirm-title">{{ t('checkout.confirm') }}</h2> ...
    </div>
  </Teleport>
</template>
```
```ts
// useFocusTrap(dialogEl, { immediate: true, returnFocusOnDeactivate: true })  (@vueuse/integrations)
router.afterEach(to => { document.title = t(to.meta.title as string); nextTick(() => document.getElementById('main')?.focus()); });
watch(locale, l => { document.documentElement.lang = l; document.documentElement.dir = ['ar','he','fa','ur'].includes(l) ? 'rtl' : 'ltr'; });
```
```css
:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.card { margin-inline-start: 1rem; text-align: start; min-width: 0; }
```

## Manual trace checklist

1. Checkout / login / order entry: keyboard only, then a screen reader; field names and
   error announcements.
2. Every `Teleport`ed overlay: focus in, trapped, restored; Escape closes; background inert.
3. Route changes: title and focus; skip link first; one `<main>` landmark.
4. Densest page at 200% zoom / 320 px; contrast of status colours and icons.
5. Switch to `de` and an RTL locale if required: truncation, mirrored icons, `$d`/`$n` output,
   plural strings.

## Stack-specific false positives

- Vuetify `v-dialog`, PrimeVue `Dialog`, Element Plus `el-dialog`, Quasar `q-dialog`, Headless UI
  `Dialog`, Radix Vue `DialogRoot`: trap and restore focus.
- `v-text-field label=`, `el-form-item label=`, `q-input label=`: labelled.
- `<img alt="">` decorative: correct.
- `$t` keys in natural language with a `messages` fallback locale: not hard-coded.
- `$tc` deprecated in vue-i18n v9+ but functional: Info, not a failure.

## Tooling

- `eslint-plugin-vuejs-accessibility` (`alt-text`, `form-control-has-label`, `click-events-have-key-events`,
  `no-autofocus`, `tabindex-no-positive`, `aria-props`): `npx eslint --ext .vue src`.
- `@intlify/eslint-plugin-vue-i18n` (`no-raw-text`, `no-missing-keys`) for hard-coded strings.
- `@axe-core/cli` / `pa11y` via `scripts/axe_runner.py`; `vue-axe` in development;
  Storybook `addon-a11y`.
- `vue-i18n-extract` to compare used keys with locale files.

## References

- Vue accessibility guide: https://vuejs.org/guide/best-practices/accessibility.html
- vue-i18n pluralization and number/date formatting: https://vue-i18n.intlify.dev/guide/essentials/pluralization.html
- VueUse `useFocusTrap`: https://vueuse.org/integrations/useFocusTrap/
- WAI-ARIA Authoring Practices: https://www.w3.org/WAI/ARIA/apg/
- WCAG 2.2 quick reference: https://www.w3.org/WAI/WCAG22/quickref/
