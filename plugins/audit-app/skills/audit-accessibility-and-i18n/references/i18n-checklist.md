# Internationalization readiness checklist

i18n findings have no single WCAG criterion. Reference `WCAG-3.1.1`/`3.1.2` when
the issue is about declared language; otherwise leave `references` empty and tag
the finding `i18n`. Severity: Medium when a second locale is planned or shipped,
Low when the product is single-locale with no plan, High when a shipped locale is
visibly broken (RTL layout, wrong plural, wrong decimal separator in money).

## 1. Strings

| Check | Pass looks like | Fail looks like | Evidence |
|---|---|---|---|
| Templates use a translation mechanism | `i18n` attr / `| translate` / `t()` / `<Trans>` / `$t` / `{% trans %}` on every user-facing text node and attribute (`placeholder`, `title`, `aria-label`, `alt`) | Literal English in templates | `template_scan.py` hard-coded count per file |
| Code-side strings go through the same mechanism | `this.translate.instant('KEY')`, `t('key')`, `_()` for toasts, dialogs, validation, `confirm()` | `toast.show('Saved')`, `alert('Are you sure?')`, Zod/Yup/DataAnnotations literal messages | grep_scan hits `HARDCODED-*` |
| Server responses carry keys or codes, not sentences | `{ code: 'QTY_NEGATIVE' }` or a localized message resolved by `Accept-Language` | `BadRequest("Quantity must be positive")` shown verbatim | backend reference file |
| No string concatenation to build sentences | ICU / interpolation with named params: `t('cart.added', { name })` | `'Added ' + name + ' to cart'` (word order differs per language) | grep `' + ` next to `t(`/text |
| Keys are stable and namespaced | `checkout.email.label` | Natural-language keys that drift, or keys reused with different meanings | locale file review |
| Locale files complete | All locales have the same keys; missing keys fall back and are logged | `ar.json` half the size of `en.json` | `i18next-parser`, `ng extract-i18n`, `makemessages` |

## 2. Dates, numbers, currency

| Check | Pass | Fail |
|---|---|---|
| Formatting uses the active locale | `Intl.DateTimeFormat(locale)`, `DatePipe` with `LOCALE_ID`, `$d`, `NumberFormat.getCurrencyInstance(locale)`, `|date:"SHORT_DATE_FORMAT"` | `toLocaleDateString()` (no arg), `moment().format('DD/MM/YYYY')`, `strftime('%d/%m/%Y')`, `toFixed(2)`, `'$' + x` |
| Currency symbol and position from locale/currency code | `style: 'currency', currency: order.currency` | `'Rs. ' + total`, `'$' + total`, symbol hard-coded in the template |
| Parsing user input respects the locale | `Number` parsed via `Intl`/locale-aware form controls; server parses with the user's culture or receives normalized values | `parseFloat(input)`, `decimal.Parse(input)` on locales using comma decimals |
| API exchanges ISO-8601 and raw numbers | `"2024-03-12T10:00:00Z"`, `1234.5` | Pre-formatted strings in JSON |
| Time zone shown is the user's | `timeZone` option or server converts per user | Server time zone leaks (owned by `audit-datetime-and-timezone`; cross-reference) |
| Digits | Locale digits where expected (`ar-EG` uses Eastern Arabic numerals; `ar` by default Latin) - decide and be consistent | Mixed numeral systems on one page |

## 3. Pluralization

| Check | Pass | Fail |
|---|---|---|
| Plural rules via ICU/CLDR | `{count, plural, =0 {none} one {# item} other {# items}}`, i18next `_one/_other` (+ `_zero/_two/_few/_many`), `ngettext`, vue-i18n `\|` forms | `n + ' items'`, `n === 1 ? 'item' : 'items'` |
| Locales with >2 forms covered | Arabic (6 forms), Russian/Polish (3-4), Urdu (2) files contain all needed categories | Only `one`/`other` in every locale file |
| Zero handled | `=0 {No items}` where the UI shows an empty state | "0 items" where "No items" was intended |
| Ordinal and range forms | `selectordinal` for "1st/2nd"; ranges use `plural` on the upper bound | "1th" |

## 4. RTL (Arabic, Hebrew, Persian, Urdu)

| Check | Pass | Fail |
|---|---|---|
| `dir` set from locale | `document.documentElement.dir = 'rtl'` on switch; `<html dir="{{ dir }}">` server-side | `dir="ltr"` hard-coded, or never set |
| Logical CSS properties | `margin-inline-start`, `padding-inline-end`, `inset-inline-start`, `text-align: start`, Tailwind `ms-/me-/ps-/pe-/start-/text-start` | `margin-left`, `padding-right`, `left: 0`, `float: left`, `text-align: left` on layout elements |
| Directional icons mirrored | Chevrons/arrows/back icons flipped via `[dir=rtl] .icon-back { transform: scaleX(-1) }` or icon set's RTL variants | Back arrow points the wrong way |
| Bidi-safe text | Numbers, phone numbers, product codes wrapped in `<bdi>` or `unicode-bidi: isolate` | Mixed Latin/Arabic strings reorder |
| Component library RTL mode | Material `Directionality`, Ionic `dir`, MUI `direction: 'rtl'` + stylis-plugin-rtl, Vuetify `rtl: true` configured | Library left in LTR while page is RTL |
| Not mirrored on purpose | Media controls, clocks, charts' time axis, phone numbers stay LTR | Everything mirrored blindly |

## 5. Text expansion and layout tolerance

| Check | Pass | Fail |
|---|---|---|
| Room for +30-50% text (German, Finnish) and +100% for short labels | `min-width` instead of `width` on buttons; labels wrap; grids use `minmax()`; `overflow-wrap: anywhere` on long words | `width: 80px` buttons, `white-space: nowrap; overflow: hidden` on labels, fixed-height cards, truncation on translated text |
| Tables and dense grids | Column widths flexible or horizontal scroll container; headers wrap | Truncated headers in the longest locale |
| Font coverage | Fonts include Arabic/Urdu (Naskh/Nastaliq) glyphs, CJK if needed; `font-display: swap`; line-height increased for Nastaliq | Tofu boxes or fallback fonts that clash |
| Sorting and searching | `localeCompare(b, locale)` / `Intl.Collator`; server collation per locale | `a > b` string comparison, `toLowerCase()` for case-insensitive (Turkish i) |
| Pseudo-localization tested | A `pseudo` locale (e.g. `[!!! Ĉĥéçķöûţ !!!]`) exists or was run once | Never tested |

## 6. Manual test script

1. Switch to the longest shipped/planned locale (`de`, else pseudo-locale): check the checkout,
   navigation, tables, buttons, toasts for truncation and overlap at 1280 px and 375 px.
2. Switch to an RTL locale (if required): layout mirrored, icons correct, numbers not
   reversed, component library in RTL mode, forms aligned.
3. On one page with money, dates, and counts: compare `en`, `de`, `ar` output for separators,
   symbols, digits, and plural forms (0, 1, 2, 5, 11 items).
4. Enter `1.234,56` in a quantity/price field under a comma-decimal locale: accepted and stored
   as 1234.56?
5. Trigger a server validation error and a toast in a non-English locale: translated?
