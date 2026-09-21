# React / Next.js reference for audit-db-schema

The schema lives in the backend; this file covers the React-side edges that
expose a bad schema and the hints React code gives about how tables are
queried. Next.js apps with Prisma/Drizzle in `app/api` or server actions are a
backend too: use `node-express.md` for those files.

## Stack markers
`package.json` with `react`, `next`; `src/`, `app/`, `pages/` folders. If `prisma/schema.prisma` or `drizzle/` exists in the same package, the backend checks apply here as well.

## Where the relevant code lives
- `src/types/*.ts`, `src/api/*.ts`, generated clients (`openapi-typescript`, `orval`, tRPC routers) - the client's view of column types.
- Form schemas: `zod`/`yup` (`z.string().max(100)`, `z.number()`), `react-hook-form` resolvers - client twin of column bounds and check constraints.
- Data tables (`@tanstack/react-table`, MUI DataGrid) `sorting`/`columnFilters` state and the query keys sent to the API - which columns are sorted/filtered (index candidates).
- Server actions / route handlers (Next.js) that call the ORM directly - full backend checklist applies.

## Dangerous / interesting APIs and patterns
- Money computed in JS `number` and posted as the authoritative total.
- `z.string()` without `.max()` on fields stored in bounded columns; `.max()` values that disagree with the column length.
- `Number(id)` on `bigint` ids; JSON ids above 2^53.
- `new Date(naiveString)` for timestamps without offset.
- `useQuery` keys carrying `sortBy`/`filter` fields - each is a server index candidate.
- Prisma `Float` on money (in Next.js monorepos), `findMany` without `where: { deletedAt: null }`, `prisma.$executeRaw` DDL at runtime.
- Client-side "soft delete" (hiding rows) while the API still returns them.

## What "good" looks like
- Server recomputes totals; the client displays `Intl.NumberFormat` output from server values.
- Validation schema constants shared with (or generated from) the backend schema.
- Ids as strings for `bigint`/UUID columns; dates as ISO-with-offset strings.

## Manual trace checklist
1. Data tables: list sortable/filterable columns -> backend index review.
2. Largest form: compare zod/yup bounds with column bounds in the checklist JSON.
3. Any money maths on the client that is persisted.
4. Next.js server code: run the full backend checklist from `node-express.md`.

## Stack-specific false positives
- `number` for display and quantities.
- Unbounded search strings not persisted.

## Tooling
- `grep -rn "z\.string()\|yup.string()" src` and `grep -rn "sortBy\|orderBy" src` to build the two lists.

## References
- `audit-api-contract`, `audit-datetime-and-timezone`, `audit-performance-and-scalability`, and `node-express.md` in this skill for Prisma/Drizzle.
