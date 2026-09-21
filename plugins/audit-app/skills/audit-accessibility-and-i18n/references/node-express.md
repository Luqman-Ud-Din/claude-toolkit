# Node / Express reference for audit-accessibility-and-i18n

This skill audits the user-facing layer. A Node backend (Express, Fastify,
NestJS, or an SSR framework server) matters when it renders HTML (EJS, Pug,
Handlebars, or SSR of the SPA), produces user-facing text (validation errors,
emails, exports), or resolves the locale. Check those; defer everything else.

## Stack markers

`package.json` with `express`/`fastify`/`@nestjs/core`; `views/**/*.ejs|pug|hbs` (server
templates); `i18next` + `i18next-http-middleware`, `i18n` (mashpie), `nestjs-i18n`
(localization present); `accept-language-parser`.

## Where the relevant code lives

`views/**`, `server.ts`/`app.ts` (locale middleware, `res.locals.lang`), validation schemas
(`joi`, `zod`, `class-validator` messages), `@nestjs/common` exception filters, `src/mail/**`
templates, export code (`exceljs`, `pdfkit`, `puppeteer` PDFs), `locales/*.json`.

## Dangerous / interesting APIs and patterns (this skill's slice only)

- Templates: `<input>` without `<label for>`; `<img>` without `alt`; literal text where
  `t('key')`/`__('key')` should be; `<html>` without `lang`; hand-rolled modals without
  `role="dialog"`.
- Validation messages hard-coded: `z.string().email('Invalid email')`, `Joi...messages({...})`
  literal, `class-validator` `@IsEmail({}, { message: 'Invalid email' })` instead of
  `i18nValidationMessage('validation.email')` (nestjs-i18n); `throw new BadRequestException('...')`
  surfaced to users; `res.status(400).send('Invalid quantity')`.
- Locale: no `Accept-Language` parsing / `i18next-http-middleware`; `moment.locale('en')` global;
  `toLocaleDateString()` without a locale on the server (uses the server's ICU/locale);
  `Intl.NumberFormat('en-US')` hard-coded; `parseFloat(userInput)` on comma-decimal locales.
- API responses pre-formatting dates (`moment().format('DD/MM/YYYY')`) and amounts
  (`toFixed(2)`, `'$' + amount`) instead of ISO strings and raw numbers.
- Plurals: `count + ' items'`, `` `${n} item${n===1?'':'s'}` ``; i18next keys without plural
  suffixes.
- Emails/SMS templates English-only; PDF exports without RTL for Arabic/Urdu; small-ICU Node
  builds (`process.versions.icu` missing / `full-icu` not installed) so `Intl` formats
  everything as `en`.

## What "good" looks like

```ts
import i18next from 'i18next'; import middleware from 'i18next-http-middleware';
i18next.use(middleware.LanguageDetector).init({ supportedLngs: ['en', 'ar', 'ur'], fallbackLng: 'en', preload: ['en','ar','ur'], backend: {...} });
app.use(middleware.handle(i18next));
// validation
const schema = z.object({ email: z.string().email({ message: 'validation.email' }) }); // key, translated by the client or req.t
// API: data, not text
res.json({ total: order.total, currency: 'PKR', createdAt: order.createdAt.toISOString() });
// server-side display (emails/PDF)
new Intl.NumberFormat(req.language, { style: 'currency', currency }).format(total);
req.t('cart.items', { count });   // cart.items_one / cart.items_other
```
```ejs
<html lang="<%= lang %>" dir="<%= ['ar','ur','he','fa'].includes(lang) ? 'rtl' : 'ltr' %>">
<label for="email"><%= t('checkout.email') %></label><input id="email" name="email" type="email" autocomplete="email">
```

## Manual trace checklist

1. Server-rendered HTML or SSR? Run `template_scan.py` over `views/` (EJS/Handlebars are HTML
   with placeholders; Pug is not - review Pug by hand) and apply the WCAG checklist.
2. Trace one validation error from schema to the client: key or literal English?
3. Locale source: header, cookie, user profile; applied to emails and exports?
4. `node -p "process.versions.icu"` and `new Intl.DateTimeFormat('ar').format(new Date())` on
   the server: full ICU present?

## Stack-specific false positives

- `toISOString()` and `Date.now()` for storage/serialization: correct.
- `Intl.*('en-US')` used to build a *canonical* string (log keys, CSV for machines): fine.
- Messages in `logger.*` calls: not user-facing.

## Tooling

`eslint-plugin-i18next` (`no-literal-string`) on server code that builds messages;
`i18next-parser` for key extraction; `npx pa11y`/`@axe-core/cli` against server-rendered
routes via `scripts/axe_runner.py`.

## Deferred to sibling skills

Time zone handling: `audit-datetime-and-timezone`. Template escaping (`<%- %>`, `{{{ }}}`):
`audit-frontend-xss-and-dom-safety`.

## References

i18next server-side: https://www.i18next.com/overview/getting-started; Node ICU:
https://nodejs.org/api/intl.html; nestjs-i18n: https://nestjs-i18n.com; WCAG 2.2: https://www.w3.org/TR/WCAG22/
