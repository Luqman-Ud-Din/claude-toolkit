# Node / Express (and NestJS, Fastify, Koa) reference for audit-datetime-and-timezone

## Stack markers
`package.json` with `express`, `@nestjs/core`, `fastify`, `koa`. Variants: ORM (Prisma, TypeORM, Sequelize, Mongoose, Knex); date library (`moment`, `dayjs`, `date-fns`, `luxon`, `Temporal` polyfill) or bare `Date`; schedulers (`node-cron`, `cron`, `agenda`, BullMQ repeat, `@nestjs/schedule`).

## Where the relevant code lives
- Models/schema: `schema.prisma` (`DateTime` -> `timestamp(3)` in Postgres, zone-less; `@db.Timestamptz` to fix), TypeORM `@Column({ type: 'timestamp' | 'timestamptz' | 'datetime' })`, Sequelize `DataTypes.DATE` (with `timezone` dialect option), Mongoose `Date` (UTC instant), Knex migrations (`table.timestamp('x', { useTz: true })`).
- Business: `services/*.ts` using `new Date()`, `Date.now()`, `moment()`, `dayjs()`, `startOf('day')`.
- Edges: DTO validation (`@IsDateString`, zod `z.string().datetime({ offset: true })`), response serialisation (`JSON.stringify` -> `toISOString()` gives `Z`), query parsing (`new Date(req.query.from)`).
- Jobs: `cron.schedule(...)`, `new CronJob(...)`, `@Cron(...)`, `repeat: { pattern }`.
- Tests: `jest.useFakeTimers`, `sinon.useFakeTimers`, `Date.now` mocks, `TZ` in `package.json` scripts (`"test": "TZ=UTC jest"` hides zone bugs).

## Dangerous / interesting APIs and patterns
- `new Date(year, month, day)` and `new Date("2024-03-10T00:00")` (local) vs `new Date("2024-03-10")` (UTC midnight): mixed in the same codebase; `setHours(0,0,0,0)` for "start of day" (process zone); `getDate()/getMonth()/getFullYear()` on instants (local components); `toLocaleDateString()` / `toString()` in API output or logs used as data.
- `moment()` / `dayjs()` without `.utc()` or `.tz(zone)`; `moment(str)` with non-ISO strings (deprecation warning, falls back to `Date` parse); `dayjs(str, 'DD/MM/YYYY')` without the customParseFormat plugin (silently wrong).
- Format strings `YYYY-MM-DD HH:mm:ss` / `DD/MM/YYYY` sent in JSON; `.format()` output stored in the DB.
- `Date.now() + 24*60*60*1000` for "tomorrow"; `.add(1, 'day')` across DST in a local zone; `diff(..., 'days')` truncating.
- Prisma `DateTime` on Postgres without `@db.Timestamptz(3)`; TypeORM `type: 'timestamp'` on Postgres; Sequelize `timezone: '+05:00'` dialect option (shifts everything); Mongoose string fields holding dates.
- Sorting: `.sort((a, b) => a.date.localeCompare(b.date))` on formatted strings; comparing `Date` objects with `==`.
- Cron: `cron.schedule('0 2 * * *', fn)` with no `timezone` option; `@Cron('0 2 * * *')` without `timeZone` in `CronOptions`; BullMQ `repeat` without `tz`.
- User zone from `req.headers['accept-language']` or `Intl.DateTimeFormat().resolvedOptions().timeZone` on the server (server's zone) instead of a stored profile field.
- Tests: `new Date()` in fixtures, `expect(dto.date).toBe(new Date().toISOString().slice(0,10))`, no `useFakeTimers`, CI pinned to `TZ=UTC` only.

## What "good" looks like
```ts
// schema.prisma
createdAt DateTime @default(now()) @db.Timestamptz(3)
invoiceDate DateTime @db.Date
// injectable clock
export const clock = { now: () => new Date() };           // replaced in tests
// day window in a stored zone (luxon)
const start = DateTime.fromISO(day, { zone: branch.ianaZone }).startOf('day').toUTC();
const end = start.plus({ days: 1 });                        // instants; DST-safe
// validation
const schema = z.object({ from: z.string().datetime({ offset: true }) });
// cron with zone
cron.schedule('0 2 * * *', run, { timezone: 'Asia/Karachi' });
```
Responses use `toISOString()` (always `Z`); date-only fields are `YYYY-MM-DD` strings typed as dates. Tests: `jest.useFakeTimers().setSystemTime(new Date('2024-03-10T01:30:00Z'))` and a CI job with `TZ=Asia/Karachi`.

## Manual trace checklist
1. Date-field map from the ORM schema: which fields are `timestamptz`/`Date`/zone-less; date-only fields stored as timestamps.
2. Every `new Date()`/`Date.now()`/`moment()`/`dayjs()` without `.utc()`: what decision it feeds and in which zone.
3. Request parsing: `new Date(req.query.x)` on strings without offset; validation schema accepts naive strings.
4. Cron/queue schedules: zone option present; job body uses UTC and the stored zone.
5. Reports: SQL `DATE(created_at)` / `date_trunc` via Knex/raw without zone; JS grouping by `getDate()`.
6. Tests: fake timers present; `TZ` pinned in scripts (note it as hiding zone bugs, not fixing them).

## Stack-specific false positives
- `new Date()` for `createdAt` stored through an ORM that maps to a UTC instant (Mongoose, Prisma `Timestamptz`): correct.
- `toISOString()` in responses: correct; `toLocaleString` in a CLI tool's console output: display only.
- `dayjs().utc()` / `moment.utc()` / `DateTime.utc()`: correct usage.
- `TZ=UTC` in Dockerfile: fine (but note tests should also run in a non-UTC zone).

## Tooling
`grep -rn "new Date(\|Date.now()\|moment(\|dayjs(\|setHours(0" src`; `grep -rn "type: 'timestamp'\|DateTime\b" schema.prisma src/**/*.entity.ts`; `npx eslint` with `eslint-plugin-no-date` or a custom `no-restricted-syntax` rule for `new Date()` outside `clock.ts`; run tests with `TZ=Asia/Karachi npm test` and again with `TZ=America/New_York`.

## References
MDN `Date` parsing caveats; Prisma `@db.Timestamptz`; TypeORM column types; node-cron `timezone` option; luxon/`Temporal` docs; ISO 8601 / RFC 3339; CWE-682, CWE-704.
