# Angular reference for audit-db-schema

The schema lives in the backend; this file covers the client-side edges that
break when the schema is wrong, and what the frontend tells you about how
tables are queried. Everything else on the client belongs to
`audit-api-contract` (DTO shape), `audit-datetime-and-timezone` (date
parsing), and `audit-frontend-best-practices`.

## Stack markers
`package.json` with `@angular/core`; `angular.json`; `tsconfig.json` path aliases (`@shared`, `@core`).

## Where the relevant code lives
- `src/app/shared/models/*.ts` - interfaces mirroring backend DTOs/entities (money as `number`, dates as `string | Date`, ids as `number`).
- `src/app/shared/validations/*`, reactive forms with `Validators.maxLength(n)`, `Validators.pattern` - the client-side twin of column bounds and check constraints.
- `core/services/api.service.ts` `buildHttpParams` and the list components - `SortColumn`/`SearchTerm`/filter keys reveal which columns the backend sorts and filters (index candidates).
- `shared/pipes` for currency/decimal formatting (`CurrencyPipe`, `DecimalPipe`, `toFixed`).

## Dangerous / interesting APIs and patterns
- Money arithmetic in TypeScript `number` (`total += line.qty * line.price`) then posted back as the source of truth - float drift compounds the schema's float problem; the server should recompute.
- `Validators.maxLength(n)` that disagrees with the column length (client allows 200, column is 100 -> 500 from the DB).
- `Number(id)` / `parseInt` on ids the backend types as `bigint` (> 2^53 loses precision; use `string`).
- Sort/filter keys sent to `GetPaginationList` (`SortColumn`, `SearchTerm`, `Status`, `BranchId`, date ranges) - list them; each must map to an index on the server side.
- `new Date(x)` on a naive timestamp string (no `Z`/offset) - parsed as local time; the fix is on the schema (`datetimeoffset`) and serialiser, not just the client.
- Free-text search inputs that hit `LIKE '%term%'` on unbounded columns (no index can help; note for the performance audit).
- Soft-deleted rows visible in dropdowns/lookups because the lookup endpoint forgot `IsDeleted == false` - manifests on the client, root cause is the missing global filter.

## What "good" looks like
- Model interfaces annotate money as `number` **for display only**; the API returns totals computed server-side and the client never re-posts computed totals.
- `Validators.maxLength` values imported from a shared constants file that mirrors the column lengths (or generated from the OpenAPI schema).
- Ids typed `string` when the backend uses `bigint`/`Guid`.
- Dates typed as ISO strings with offset and converted with the app's date service at the edge.

## Manual trace checklist
1. Open the main list pages (sales, purchases, products, stock): note filter and sort fields -> hand them to the backend index review.
2. Open the biggest form (product, invoice): compare `maxLength` validators to the column bounds in the checklist JSON.
3. Find any place the client sums money and posts the total.

## Stack-specific false positives
- `number` for quantities and display of money is fine when the server recomputes.
- Missing `maxLength` on search inputs (not persisted).

## Tooling
- `grep -rn "Validators.maxLength" src/app` and `grep -rn "SortColumn\|OrderBy" src/app` to build the two lists quickly.

## References
- Angular reactive forms validators; `audit-api-contract`, `audit-datetime-and-timezone`, `audit-performance-and-scalability` for the rest.
