# Angular reference for audit-datetime-and-timezone

## Stack markers
`package.json` with `@angular/core`, `angular.json`. Variants: `DatePipe`/`formatDate` only, or `moment`/`dayjs`/`date-fns`/`luxon`; Angular Material datepicker (`MatNativeDateModule` vs `MatMomentDateModule`/`MatLuxonDateModule`); Ionic `ion-datetime`; `@angular/localize` locales; Capacitor mobile (device zone changes on travel).

## Where the relevant code lives
- Parsing of API values: `core/services/api.service.ts`, HTTP interceptors that convert strings to `Date` (`new Date(value)`, `reviver`), `shared/models/*.ts` typing dates as `string | Date`.
- Display: templates with `| date:'dd/MM/yyyy'` / `| date:'short'` (no zone label unless `'z'`), `formatDate(value, format, locale, timezone)`.
- Input: reactive forms with datepickers, `ion-datetime` (`value` is ISO local), `<input type="date">` (yields `YYYY-MM-DD`), `<input type="datetime-local">` (no offset).
- Client-side rules: "today" filters (`new Date().toDateString()`), `isExpired` computed in the browser, date range presets in report screens.
- Tests: `jasmine.clock().mockDate`, `new Date()` in specs.

## Dangerous / interesting APIs and patterns
- `new Date('2024-03-10')` (date-only string parses as UTC midnight, displays as 9 March in zones west of UTC) versus `new Date('2024-03-10T00:00')` (local); `new Date('10/03/2024')` (implementation-defined); `Date.parse` on `dd-MM-yyyy`.
- API strings without offset (`2024-03-10T14:30:00`) passed to `new Date()`: treated as local, so each user sees a different instant; the fix is on the API, but record the client site as evidence.
- Sending `date.toString()` / `toLocaleDateString()` / `formatDate(d, 'yyyy-MM-dd HH:mm')` to the backend; posting `new Date()` of a date picker as `toISOString()` for a date-only field (shifts the day for UTC+ zones: 10 March 00:00 PKT becomes `2024-03-09T19:00:00Z`).
- `setHours(0,0,0,0)` / `startOf('day')` in the browser used to build report ranges sent to the server (browser zone, not branch zone).
- `DatePipe` without the `timezone` argument when the app shows branch-local times to users in other zones; no zone label on timestamps (`'z'`/`'ZZZZZ'` missing) where users span zones.
- `moment(str, 'DD/MM/YYYY')` round-tripped to the API; `dayjs(str)` without `utc` plugin; sorting table columns on the formatted string (`sortBy(row => row.dateLabel)`).
- User zone guessed with `Intl.DateTimeFormat().resolvedOptions().timeZone` and never stored server-side (changes when the user travels; server cannot reproduce).
- `MatNativeDateModule` with `useUtc` unset: picker values are local midnight `Date` objects; components then call `toISOString()`.
- Specs using real `new Date()`; `jasmine.clock()` never installed; Karma running only in the developer's zone.

## What "good" looks like
```ts
// model: keep instants as ISO strings with offset until display
export interface Order { createdAt: string /* 2024-03-10T09:30:00Z */; invoiceDate: string /* 2024-03-10 */; }
// display in the branch zone with a label
{{ order.createdAt | date:'medium':branchOffset }}   // branchOffset like '+0500', from the stored branch zone
// date-only: send the picker's calendar date, not an instant
const invoiceDate = formatDate(picker.value, 'yyyy-MM-dd', locale);   // no toISOString()
// report ranges: send the calendar dates and let the server apply the branch zone
this.api.post('/reports/sales', { from: '2024-03-01', to: '2024-03-31', branchId });
// tests
beforeEach(() => { jasmine.clock().install(); jasmine.clock().mockDate(new Date('2024-03-10T01:30:00Z')); });
```
For date+time input use a zone-aware library (luxon `DateTime.fromISO(v, { zone })`) and post `toUTC().toISO()`.

## Manual trace checklist
1. Every `new Date(` / `Date.parse(` on API or user strings: what format the string is, and whether it has an offset.
2. Every outgoing date in `api.service.ts`/feature services: `toISOString()` vs formatted string vs calendar date; date-only fields shifted by `toISOString()`.
3. Report/dashboard range builders: computed in browser zone and sent as instants?
4. Display: `DatePipe` timezone argument and zone label for cross-zone users; relative-time pipes based on parsed naive strings.
5. Stored user/branch zone: does the UI read it from the profile or guess it.
6. Specs: real-time usage; `jasmine.clock` present.

## Stack-specific false positives
- `new Date(isoWithOffset)` and `new Date(epochMillis)`: correct parsing.
- `| date:'short'` on an instant shown to the user in their own browser zone, when the product's users are all in that zone (record the assumption).
- `toISOString()` for true instants (created/updated timestamps).
- `<input type="date">` values sent as `YYYY-MM-DD` strings.

## Tooling
`grep -rn "new Date(\|Date.parse(\|setHours(0\|toLocaleDateString\|toISOString" src/app --include=*.ts`; `grep -rn "| date:" src/app --include=*.html | grep -v "'z'\|ZZZZ"`; run `ng test` with `TZ=America/New_York` and again with `TZ=Asia/Karachi`; Chrome DevTools "Sensors" panel to override the browser zone.

## References
Angular `DatePipe`/`formatDate` docs (timezone argument); MDN `Date` string parsing; ISO 8601; luxon docs; the backend reference for this stack pair owns the API format finding.
