# Vue (and Nuxt) reference for audit-datetime-and-timezone

## Stack markers
`package.json` with `vue` or `nuxt`. Variants: Vue 2/3; Nuxt SSR with `server/api/**` (server code: audit with `node-express.md`); date libraries (`dayjs`, `date-fns`, `luxon`, `moment`, `@vuepic/vue-datepicker`, Vuetify `v-date-picker`, Element Plus `el-date-picker` with `value-format`); `vue-i18n` `$d()` formatting.

## Where the relevant code lives
- Parsing: `services/api.ts`, Pinia store actions mapping responses (`new Date(r.createdAt)`), `useFetch` transforms, zod schemas.
- Display: `$d(date, 'long')`, `dayjs(x).format('DD/MM/YYYY')`, computed labels, filters (Vue 2).
- Input: pickers (`el-date-picker` `value-format="YYYY-MM-DD"` vs default `Date`), `<input type="date">`, `datetime-local`.
- Client rules: `isExpired` computed, "today" highlights, report presets (`dayjs().startOf('month')`).
- Nuxt SSR: server formats in UTC, client in browser zone: hydration mismatch and date flip.
- Tests: `vi.useFakeTimers`, `vi.setSystemTime`, `new Date()` in specs, `TZ` in test script.

## Dangerous / interesting APIs and patterns
- `new Date('2024-03-10')` (UTC midnight) then `.getDate()`/`format` in a western zone; `new Date(apiStringWithoutOffset)` treated as local, different per user.
- `dayjs(str)` without the `utc`/`timezone` plugins; `dayjs(str, 'DD/MM/YYYY')` without `customParseFormat`; `moment(str)` non-ISO.
- Posting `toISOString()` of a picker `Date` for a date-only field (day shift east of UTC); posting `dayjs().format('YYYY-MM-DD HH:mm:ss')` (no offset) for instants.
- `dayjs().startOf('day')` / `setHours(0,0,0,0)` for report ranges sent as instants (browser zone, not branch zone).
- `el-date-picker` without `value-format` for date-only fields (emits local-midnight `Date`); with `value-format="x"` (epoch of local midnight).
- `Intl.DateTimeFormat().resolvedOptions().timeZone` as the user's zone, never stored server-side.
- Sorting on formatted strings in table components; grouping by `getDate()`.
- Nuxt `useState`/SSR rendering `toLocaleString()` on the server; `<ClientOnly>` used to hide the mismatch rather than pass a zone.
- Tests: `expect(wrapper.text()).toContain('10/03/2024')` from `new Date()`; `TZ=UTC` only.

## What "good" looks like
```ts
// keep instants as ISO strings; convert once for display with an explicit zone
const shown = computed(() => DateTime.fromISO(order.value.createdAt).setZone(branch.value.ianaZone).toFormat('dd LLL yyyy HH:mm ZZZZ'));
// date-only picker: emit the calendar date
<el-date-picker v-model="invoiceDate" type="date" value-format="YYYY-MM-DD" />
// ranges: send calendar dates + branch, let the server apply the zone
await api.post('/reports/sales', { from: '2024-03-01', to: '2024-03-31', branchId });
// tests
vi.useFakeTimers(); vi.setSystemTime(new Date('2024-03-10T01:30:00Z'));
```
For date+time input: luxon `DateTime.fromISO(v, { zone })` then `toUTC().toISO()`. Nuxt: format in client components or pass the zone to both sides.

## Manual trace checklist
1. Every `new Date(`/`dayjs(`/`moment(`/`parseISO(` on API or user strings: format and offset presence.
2. Outgoing dates in store actions/services: instants vs calendar dates; `toISOString()` on date-only pickers; `value-format` on pickers.
3. Report/dashboard range builders computed in the browser and sent as instants.
4. Display: explicit zone and label where users span zones; SSR/CSR mismatch.
5. Stored user/branch zone vs `Intl` guess.
6. Tests: fake timers, `TZ` pinning, DST cases.
7. Nuxt server routes: apply `node-express.md`.

## Stack-specific false positives
- `new Date(isoWithOffset)`, `dayjs.utc(iso)`, `new Date(epochMs)`: correct.
- `$d()`/`toLocaleString()` in client-only components for a single-zone user base (record the assumption).
- `toISOString()` for true instants.
- `<input type="date">`/`value-format="YYYY-MM-DD"` posted as calendar dates.

## Tooling
`grep -rn "new Date(\|dayjs(\|startOf('day')\|toISOString\|toLocaleDateString" src --include=*.ts --include=*.vue`; `grep -rn "date-picker" src --include=*.vue | grep -v value-format`; run tests with `TZ=Asia/Karachi` and `TZ=America/Los_Angeles`; ESLint `no-restricted-syntax` for `new Date()` outside `clock.ts`.

## References
MDN `Date` parsing; dayjs `utc`/`timezone` plugins; Element Plus `value-format`; Nuxt hydration docs; ISO 8601; the backend reference owns the API format finding.
