# Angular reference for audit-accessibility-and-i18n

## Stack markers

`package.json` with `@angular/core`; i18n mechanism is one of `@angular/localize`
(`i18n` attributes, `$localize`, `angular.json` `i18n.locales`), `@ngx-translate/core`
(`| translate`, `assets/i18n/*.json`), or `transloco` (`| transloco`, `t()`). UI kits change
the a11y baseline: Angular Material / CDK (a11y built in), Ionic (`ion-*` components with
built-in labels and focus management), PrimeNG, ng-bootstrap.

## Where the relevant code lives

`*.component.html` and inline `template:` strings; `app.routes.ts` (route titles via
`title:` and `TitleStrategy`); `app.component.html` (skip link, `<main>`, `<router-outlet>`);
`index.html` (`<html lang>`, `dir`); `styles.scss` (focus styles, logical properties);
`assets/i18n/*.json` or `src/locale/messages.*.xlf`; `app.config.ts` (`LOCALE_ID`,
`registerLocaleData`, `provideRouter(..., withInMemoryScrolling(...))`); pipes (`date`,
`number`, `currency`) and any custom formatting service.

## Dangerous / interesting APIs and patterns

- Inputs with only `placeholder`, no `<label for>`, `aria-label`, `[attr.aria-label]`, or
  `<mat-label>`; `<ion-input>` without `label`/`aria-label` or a sibling `<ion-label>`.
- `<img [src]>` without `alt`/`[alt]`; `<mat-icon>`/`<ion-icon>` inside a button with no text
  and no `aria-label`; `<svg>` without `aria-hidden="true"` or a `<title>`.
- Custom dialogs: `<div class="modal" *ngIf="open">` without `cdkTrapFocus`, `role="dialog"`,
  `aria-modal="true"`, `aria-labelledby`; no focus restore on close. `MatDialog` and
  `ion-modal` handle this; hand-rolled overlays do not.
- `(click)` on `<div>`/`<span>`/`<li>` without `role="button"`, `tabindex="0"`, and
  `(keydown.enter)`/`(keydown.space)`.
- `tabindex` greater than 0; `autofocus` on page load in a non-dialog context.
- Route change: no `TitleStrategy`/`title:` on routes (2.4.2); no focus management after
  navigation (focus stays on the removed link) - `LiveAnnouncer` or focusing `<h1>`.
- `*ngFor` tables without `<th scope>`; `<table>` used for layout; headings skipped (h1 -> h3).
- Colour-only status: `[class.red]="status==='error'"` with no text/icon.
- Focus styles removed: `outline: none` in `styles.scss` without a `:focus-visible` rule.
- i18n: text nodes in templates without `i18n` attr / `| translate` / `| transloco`; literal
  `placeholder="..."`, `title="..."`, `aria-label="..."` without `i18n-placeholder` etc.;
  strings in `.ts` (`this.toast.show('Saved')`, validation messages, `confirm('Delete?')`).
- Formatting: `new Date().toLocaleDateString()` with no locale; `.toFixed(2)` for money;
  `'$' + price`; `{{ d | date:'dd/MM/yyyy' }}` (fixed pattern instead of `'shortDate'`);
  `DatePipe` without `LOCALE_ID` provided; `formatNumber` with hard-coded `'en-US'`.
- Plurals: `count + ' items'`, `count === 1 ? 'item' : 'items'`; no ICU (`{count, plural, ...}`).
- RTL: `margin-left`, `padding-right`, `text-align: left`, `float: left`, `left: 0` instead
  of logical `margin-inline-start` etc.; `dir="ltr"` hard-coded; icons with direction
  (arrows, chevrons) not mirrored; `[dir]` not bound from the locale.
- Text expansion: `width: 80px` on buttons/labels, `white-space: nowrap` + `overflow: hidden`
  on translated text, fixed-height cards.

## What "good" looks like

```html
<a class="skip-link" href="#main" i18n>Skip to content</a>
<main id="main" tabindex="-1">
  <h1 i18n="@@checkoutTitle">Checkout</h1>
  <label for="email" i18n>Email</label>
  <input id="email" type="email" formControlName="email" autocomplete="email"
         [attr.aria-invalid]="f.email.invalid && f.email.touched" aria-describedby="email-err">
  <p id="email-err" role="alert" *ngIf="f.email.touched && f.email.invalid" i18n>Enter a valid email</p>
  <img [src]="product.image" [alt]="product.name">
  <button type="button" (click)="remove(item)" [attr.aria-label]="'Remove ' + item.name"><mat-icon aria-hidden="true">delete</mat-icon></button>
  <p>{{ total | currency:currencyCode:'symbol':'1.2-2' }} - {{ today | date:'mediumDate' }}</p>
  <p i18n>{count, plural, =0 {No items} =1 {One item} other {{{count}} items}}</p>
</main>
<div *ngIf="confirmOpen" role="dialog" aria-modal="true" aria-labelledby="confirm-title"
     cdkTrapFocus [cdkTrapFocusAutoCapture]="true">
  <h2 id="confirm-title" i18n>Confirm order?</h2> ...
</div>
```
```scss
:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }
.card { margin-inline-start: 1rem; padding-inline: 1rem; text-align: start; min-width: 0; }
```
```ts
// app.config.ts
provideRouter(routes, withInMemoryScrolling({ scrollPositionRestoration: 'top' })),
{ provide: LOCALE_ID, useFactory: (i: I18nService) => i.locale, deps: [I18nService] },
// on route change: document.documentElement.dir = rtlLocales.includes(locale) ? 'rtl' : 'ltr'
```

## Manual trace checklist

1. Checkout / order entry / login: keyboard only, then NVDA or VoiceOver; every field
   announced with name, every error announced (`role="alert"` or `aria-live`).
2. Every custom overlay (`*ngIf` modals, side panels, dropdown menus): focus in, trapped,
   restored; Escape closes.
3. Route changes: title updates (`TitleStrategy`), focus moves to `<main>`/`<h1>`, skip link
   is the first tab stop on every page.
4. Densest data page at 200% zoom and 320 px width; status colours pass 4.5:1 (text) /
   3:1 (icons, borders).
5. Switch locale to `de` (longest) and `ar` (RTL, if required): layout, mirrored chevrons,
   dates/numbers/currency, plural strings.

## Stack-specific false positives

- `<mat-form-field>` with `<mat-label>`: labelled. `<ion-input label="...">` or `<ion-item>`
  with `<ion-label>`: labelled. `<mat-checkbox>Text</mat-checkbox>`: labelled by content.
- `MatDialog`, `ion-modal`, `ion-alert`, `MatBottomSheet`, `CdkDialog`: trap and restore focus.
- `<img alt="">` on decorative images: correct, not a finding.
- `mat-icon` with `aria-hidden` inside a button that has text: fine.
- `i18n` attribute present but untranslated in other locales: not this skill's problem
  (translation completeness is a project-management item; note it under Not checked).
- `| date` without a format uses `'mediumDate'` with `LOCALE_ID`: fine if `LOCALE_ID` is set.

## Tooling

- `@angular-eslint/template` a11y rules: `alt-text`, `elements-content`, `label-has-associated-control`,
  `click-events-have-key-events`, `interactive-supports-focus`, `no-positive-tabindex`,
  `role-has-required-aria`, `valid-aria`, `i18n` (flags untranslated text). Run:
  `npx ng lint` after adding `plugin:@angular-eslint/template/accessibility`.
- `npx @axe-core/cli http://localhost:4200/checkout --tags wcag2a,wcag2aa,wcag21aa,wcag22aa`
  (via `scripts/axe_runner.py`); `npx pa11y`; Lighthouse "Accessibility" category.
- `ng extract-i18n` (localize) shows how many strings are marked; compare with
  `template_scan.py`'s hard-coded count.
- Chrome DevTools > Rendering > "Emulate vision deficiencies"; CSS Overview for contrast.
- `@angular/cdk/a11y`: `FocusTrap`, `LiveAnnouncer`, `FocusMonitor`, `cdkAriaLive`.

## References

- Angular accessibility guide: https://angular.dev/best-practices/a11y
- Angular i18n: https://angular.dev/guide/i18n; ngx-translate messageformat compiler for plurals.
- CDK a11y: https://material.angular.io/cdk/a11y/overview
- WCAG 2.2 quick reference: https://www.w3.org/WAI/WCAG22/quickref/
- Unicode CLDR plural rules: https://cldr.unicode.org/index/cldr-spec/plural-rules
