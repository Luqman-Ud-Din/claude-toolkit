# Vue / Nuxt reference for audit-db-schema

The schema lives in the backend; this file covers the Vue-side edges. Nuxt
`server/` routes that use Prisma/Drizzle/Knex are backend code: use
`node-express.md` for them.

## Stack markers
`package.json` with `vue`, `nuxt`; `src/` or `pages/`, `components/`, `stores/` (Pinia), `server/` (Nuxt).

## Where the relevant code lives
- `src/types/*.ts`, `composables/useApi*.ts`, generated clients - the client's view of column types.
- Form validation: `vee-validate` + `yup`/`zod` schemas, Vuetify/Element Plus `rules` (`v => v.length <= 100`) - client twin of column bounds.
- Tables (`v-data-table-server`, Element `el-table` with `@sort-change`) and Pinia stores holding `sortBy`/`filters` - which columns are sorted/filtered (index candidates).
- Nuxt `server/api/*.ts`, `server/utils/db.ts` - full backend checklist applies.

## Dangerous / interesting APIs and patterns
- Money summed in JS and posted as the total.
- Validation rules with bounds that differ from column lengths, or no bound at all for persisted fields.
- `Number(id)` on `bigint` ids; `new Date(naiveString)` for timestamps.
- Sort keys passed straight through to the API (`sortBy[0].key`) - each needs an index server-side; also a whitelist concern for `audit-injection-vulnerabilities`.
- Nuxt server code: Prisma `Float` money, missing `@@index`, `deletedAt` not filtered.

## What "good" looks like
- Server recomputes totals; client formats with `Intl.NumberFormat`.
- Shared validation constants mirroring column bounds.
- Ids as strings for `bigint`/UUID; ISO-with-offset dates.

## Manual trace checklist
1. Server-side tables: list sort/filter keys -> backend index review.
2. Largest form: compare rules with column bounds in the checklist JSON.
3. Any persisted client-side money arithmetic.
4. Nuxt `server/`: full backend checklist from `node-express.md`.

## Stack-specific false positives
- `number` for display/quantities; unbounded search inputs not persisted.

## Tooling
- `grep -rn "sort-change\|sortBy" src` and `grep -rn "max(\|maxLength" src`.

## References
- `audit-api-contract`, `audit-datetime-and-timezone`, `audit-performance-and-scalability`, `node-express.md` in this skill.
