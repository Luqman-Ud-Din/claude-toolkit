# React reference for audit-accessibility-and-i18n

## Stack markers

`package.json` with `react`; `next` for Next.js (adds `next/head` titles, `next-intl` /
`next-i18next` for i18n, `app/[locale]` routing). i18n libraries: `react-i18next`
(`useTranslation`, `t()`, `<Trans>`), `react-intl` (`FormattedMessage`, `formatMessage`,
`FormattedNumber`), `lingui` (`t` macro, `<Trans>`), `next-intl` (`useTranslations`).
UI kits: MUI, Chakra, Radix, Headless UI, React Aria (a11y built in); Ant Design (mostly);
Tailwind UI (markup only - no behaviour).

## Where the relevant code lives

`src/components/**/*.tsx`, `src/pages/**` or `app/**` (Next), `index.html` / `app/layout.tsx`
(`<html lang dir>`), `src/router.tsx` (route titles, focus reset), `src/i18n.ts` /
`locales/*.json`, global CSS / Tailwind config (focus styles, logical utilities `ms-`/`me-`),
`src/utils/format.ts` (dates, numbers, currency).

## Dangerous / interesting APIs and patterns

- `<input placeholder="...">` without `<label htmlFor>`, `aria-label`, or `aria-labelledby`;
  `<label>` present but `htmlFor` missing or `id` mismatched.
- `<img src>` without `alt`; Next `<Image>` also requires `alt`; icon libraries (`react-icons`,
  `lucide-react`) inside a button with no text and no `aria-label`.
- Custom modals: `{open && <div className="modal">}` without `role="dialog"`, `aria-modal`,
  `aria-labelledby`, a focus trap (`focus-trap-react`, `react-focus-lock`, `useFocusTrap`), or
  focus restore. `<dialog>` element without `.showModal()` (only `showModal` traps focus).
- `onClick` on `<div>`/`<span>` without `role`, `tabIndex={0}`, and `onKeyDown`;
  `<a>` without `href` used as a button.
- `tabIndex` greater than 0; `autoFocus` on page load.
- Route changes (react-router): no `document.title` update / `<title>` (Next `metadata`) and
  no focus management (`useEffect` on location to focus `<main>`).
- `dangerouslySetInnerHTML` rendering content with no headings/landmarks (also XSS skill).
- Colour-only status (`className={ok ? 'text-green' : 'text-red'}` with no text/icon).
- `outline-none` (Tailwind) / `outline: none` without `focus-visible:` alternative.
- i18n: JSX text nodes and attribute strings outside `t()`/`<Trans>`/`<FormattedMessage>`;
  strings in hooks and stores (`toast.success('Saved')`, Zod/Yup messages, `alert()`).
- Formatting: `toLocaleDateString()` / `toLocaleString()` with no locale argument;
  `.toFixed(2)`, `'$' + price`, `moment().format('DD/MM/YYYY')`, `dayjs().format(...)` fixed
  pattern; `Intl.NumberFormat('en-US', ...)` hard-coded; `new Date(str).getDate()` in local time.
- Plurals: `` `${n} item${n === 1 ? '' : 's'}` ``, `n + ' items'`; i18next keys without
  `_one`/`_other` suffixes; `FormattedMessage` without `plural` ICU.
- RTL: `ml-`/`mr-`/`pl-`/`pr-`/`text-left`/`left-0` Tailwind utilities instead of `ms-`/`me-`/
  `ps-`/`pe-`/`text-start`/`start-0`; `dir="ltr"` on `<html>`; directional icons not mirrored;
  `style={{ marginLeft }}` inline.
- Text expansion: `w-24` / `width: 96px` on buttons, `truncate` on translatable labels,
  `h-10` fixed on multi-line text.

## What "good" looks like

```tsx
export function CheckoutForm() {
  const { t, i18n } = useTranslation();
  const nf = useMemo(() => new Intl.NumberFormat(i18n.language, { style: 'currency', currency }), [i18n.language]);
  return (
    <main id="main" tabIndex={-1}>
      <h1>{t('checkout.title')}</h1>
      <label htmlFor="email">{t('checkout.email')}</label>
      <input id="email" type="email" autoComplete="email" aria-invalid={!!errors.email}
             aria-describedby={errors.email ? 'email-err' : undefined} {...register('email')} />
      {errors.email && <p id="email-err" role="alert">{t('checkout.emailInvalid')}</p>}
      <img src={product.image} alt={product.name} />
      <button type="button" aria-label={t('cart.remove', { name: item.name })}><TrashIcon aria-hidden /></button>
      <p>{nf.format(total)} - {new Intl.DateTimeFormat(i18n.language, { dateStyle: 'medium' }).format(today)}</p>
      <p>{t('cart.items', { count })}</p>   {/* cart.items_one / cart.items_other in locale files */}
    </main>
  );
}
// Dialog: use Radix/Headless UI/React Aria, or:
<FocusLock returnFocus><div role="dialog" aria-modal="true" aria-labelledby="t">...</div></FocusLock>
```
```css
:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.card { margin-inline-start: 1rem; text-align: start; min-width: 0; }
```
Set `document.documentElement.dir = i18n.dir()` on language change (i18next) and use
Tailwind logical utilities (`ms-4`, `pe-2`, `text-start`, `start-0`).

## Manual trace checklist

1. Checkout / login / order entry: keyboard only, then a screen reader; names on every field,
   errors announced, submit reachable.
2. Every custom overlay: focus in, trapped, restored; Escape closes; background inert
  (`inert` attribute or `aria-hidden` on siblings).
3. Route changes: title and focus; skip link first on each page; `<main>` landmark present
   once.
4. Densest page at 200% zoom / 320 px; contrast of status colours and icons.
5. Switch to `de` and an RTL locale (if required): truncation, mirrored icons, formats,
   plural strings.

## Stack-specific false positives

- Radix `Dialog`, Headless UI `Dialog`, React Aria `useDialog`, MUI `Dialog`, Chakra `Modal`:
  trap and restore focus, set `aria-modal`.
- MUI `TextField label=`, Chakra `FormLabel`, React Aria `TextField`: labelled.
- `<img alt="">` on decorative images: correct.
- `t('key')` with a key that *looks* like English ("Save") when the library uses natural-language
  keys (lingui, i18next with `keySeparator: false`): not hard-coded.
- Tailwind `sr-only` labels: labelled (visually hidden is fine).
- `outline-none` immediately followed by `focus-visible:ring-*`: fine.

## Tooling

- `eslint-plugin-jsx-a11y` (`alt-text`, `label-has-associated-control`, `click-events-have-key-events`,
  `no-noninteractive-element-interactions`, `no-autofocus`, `tabindex-no-positive`): run
  `npx eslint src --ext .tsx`; absence of the plugin is itself an Info finding.
- `eslint-plugin-i18next` (`no-literal-string`) or `eslint-plugin-formatjs` for hard-coded strings.
- `@axe-core/react` in development logs violations to the console; `@axe-core/cli` /
  `pa11y` via `scripts/axe_runner.py`; Storybook `@storybook/addon-a11y`; `jest-axe` in tests.
- `i18next-parser` / `lingui extract` to count extracted keys vs `template_scan.py` totals.

## References

- React accessibility docs: https://react.dev/learn/accessibility (and legacy https://legacy.reactjs.org/docs/accessibility.html)
- WAI-ARIA Authoring Practices (dialog, menu, combobox patterns): https://www.w3.org/WAI/ARIA/apg/
- react-i18next plurals: https://www.i18next.com/translation-function/plurals
- Tailwind logical properties: https://tailwindcss.com/docs/margin#using-logical-properties
- WCAG 2.2 quick reference: https://www.w3.org/WAI/WCAG22/quickref/
