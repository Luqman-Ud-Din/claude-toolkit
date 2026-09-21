# React (and Next.js) reference for audit-datetime-and-timezone

## Stack markers
`package.json` with `react` or `next`. Variants: SPA (Vite/CRA) vs Next.js with server components / route handlers (server code: audit with `node-express.md`); date libraries (`date-fns`, `dayjs`, `luxon`, `moment`, `react-datepicker`, MUI `DatePicker` with `AdapterDateFns`/`AdapterLuxon`); `react-intl`/`i18next` formatting.

## Where the relevant code lives
- Parsing: `services/api.ts`, React Query `select`/`transform` functions, zod response schemas (`z.coerce.date()` accepts naive strings), `JSON.parse` revivers.
- Display: components using `format(date, 'dd/MM/yyyy')`, `Intl.DateTimeFormat`, `toLocaleString`, `formatDistanceToNow`.
- Input: `react-datepicker`, MUI pickers (`value` is a local `Date`/`Dayjs`), `<input type="date">`, `datetime-local`.
- Client rules: "today" badges, `isPast(expiresAt)`, report presets (`startOfMonth(new Date())`).
- Next.js hydration: server renders in UTC, client re-renders in browser zone; mismatched output -> hydration warnings and a visible date flip.
- Tests: `jest.useFakeTimers`, `vi.setSystemTime`, `new Date()` in fixtures, `TZ` in `package.json` test script.

## Dangerous / interesting APIs and patterns
- `new Date('2024-03-10')` (UTC midnight) rendered with `getDate()`/`format` in a western zone shows 9 March; `new Date(apiStringWithoutOffset)` treated as local.
- `date-fns` `parse(str, 'dd/MM/yyyy', new Date())` on API strings; `parseISO('2024-03-10T14:30:00')` (no offset: local); `formatISO(date)` for date-only pickers (includes local offset time).
- Posting `toISOString()` of a picker value for a date-only field (day shift east of UTC); posting `toLocaleDateString()`.
- `startOfDay(new Date())` / `dayjs().startOf('day')` for ranges sent to the server as instants (browser zone, not branch zone); `endOfDay` used as "expires at end of day" client-side.
- `Intl.DateTimeFormat().resolvedOptions().timeZone` used as the user's zone without storing it server-side.
- Sorting table rows on formatted strings (`a.dateLabel.localeCompare(b.dateLabel)`); `useMemo` grouping by `getDate()`.
- Server components / SSR formatting dates with `toLocaleString()` (server zone) then client re-formatting (hydration mismatch); `suppressHydrationWarning` used to hide it.
- Timers: `setInterval` countdowns computed from `Date.now()` minus a naive parsed value.
- Tests: `expect(screen.getByText('10/03/2024'))` against `new Date()`; `TZ=UTC` in the test script hiding zone bugs; no fake timers.

## What "good" looks like
```tsx
// keep instants as ISO strings; convert once for display with an explicit zone
const shown = DateTime.fromISO(order.createdAt, { zone: 'utc' }).setZone(branch.ianaZone).toFormat('dd LLL yyyy HH:mm ZZZZ');
// date-only: send the calendar date the user picked
const invoiceDate = format(picker, 'yyyy-MM-dd');            // not toISOString()
// ranges: send calendar dates + branch, let the server apply the zone
mutate({ from: '2024-03-01', to: '2024-03-31', branchId });
// tests
vi.useFakeTimers(); vi.setSystemTime(new Date('2024-03-10T01:30:00Z'));
```
Response schemas: `z.string().datetime({ offset: true })` for instants, `z.string().date()` for date-only. Next.js: format on the client only (`useEffect`/client component) or pass the zone explicitly to both sides.

## Manual trace checklist
1. Every `new Date(`/`parseISO(`/`dayjs(`/`moment(` on API or user strings: format and offset presence.
2. Outgoing dates in mutations: instants vs calendar dates; `toISOString()` on date-only pickers.
3. Report/dashboard range builders computed in the browser and sent as instants.
4. Display: explicit zone and label where users span zones; SSR/CSR formatting mismatch.
5. Stored user/branch zone vs `Intl` guess.
6. Tests: fake timers, `TZ` pinning, DST cases.
7. Next.js route handlers/server actions: apply `node-express.md`.

## Stack-specific false positives
- `new Date(isoWithOffset)`, `parseISO('...Z')`, `new Date(epochMs)`: correct.
- `toLocaleString()` in a client-only component for a single-zone user base (record the assumption).
- `toISOString()` for true instants.
- `<input type="date">` posted as `YYYY-MM-DD`.

## Tooling
`grep -rn "new Date(\|parseISO(\|startOfDay(\|toISOString\|toLocaleDateString" src --include=*.ts --include=*.tsx`; `grep -rn "suppressHydrationWarning" src`; run tests with `TZ=Asia/Karachi` and `TZ=America/Los_Angeles`; ESLint `no-restricted-syntax` for `new Date()` outside a `clock.ts`.

## References
MDN `Date` parsing; date-fns `parseISO`/`formatISO` docs; luxon zones; Next.js hydration mismatch docs; ISO 8601; the backend reference owns the API format finding.
