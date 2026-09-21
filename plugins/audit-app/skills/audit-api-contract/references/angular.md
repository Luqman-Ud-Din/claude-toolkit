# Angular reference for audit-api-contract

## Stack markers
`package.json` with `@angular/core`, `angular.json`. Variants: hand-written `api.service.ts` vs generated clients (`openapi-generator`, `ng-openapi-gen`, `nswag` TypeScript client); interceptors for errors; `proxy.conf.json` mapping API prefixes.

## Where the relevant code lives
The server owns the contract; the frontend shows (a) which endpoints and fields clients actually depend on (so removals in the spec diff can be mapped to real breakage), (b) how many distinct error shapes clients have to parse (evidence for the consistency finding), and (c) contract drift where the client and server disagree. Look in `core/services/api.service.ts`, `core/interceptors/*.ts` (error handling), `shared/models/*.ts` (client-side DTOs), feature services (`features/**/services/*.service.ts`), `environments/*.ts` (base URLs, version prefixes), `proxy.conf.json`, and any generated client folder.

## Dangerous / interesting APIs and patterns
- Multiple error parsers: `err.error.message`, `err.error.error`, `err.error.detail`, `err.error.errors[0]`, `err.error.title` handled in different services or one interceptor with a chain of fallbacks: each branch is a distinct server shape (count them and cite the files in the API-side finding).
- Unversioned base URLs: `environment.apiUrl = '/api'` with routes like `/api/orders` and `/api/v2/orders` mixed in services.
- Client models declaring fields the server should not send (`passwordHash`, `isDeleted`, `companyId` of other tenants, `costPrice` on a customer-facing model): evidence of over-exposure the backend finding cites.
- Client-side pagination of an unpaginated response (`slice(page * size, ...)` on a full array, `MatPaginator` bound to a full list) - proof the list endpoint returns everything.
- Manual query-key translation (`PageNumber`, `PageSize`, `SearchTerm`) in `buildHttpParams`: a contract that exists only in code; flag when it diverges from the server's parameter names.
- Dates parsed with `new Date(x)` on strings without offset (hand to the datetime skill), `dd/MM/yyyy` strings posted back.
- Numeric ids as strings in some calls (`${id}` vs `id`), casing differences (`OrderId` vs `orderId`) between models: contract drift.
- Generated client committed but stale (compare `swagger.json` hash or a few operations with the server).

## What "good" looks like
```ts
// one error shape, one interceptor
catchError((err: HttpErrorResponse) => {
  const problem = err.error as ProblemDetails;       // { type, title, status, detail, errors? }
  this.notify.error(problem?.title ?? 'Request failed', problem?.errors);
  return throwError(() => problem);
})
// versioned base URL and typed DTOs generated from the spec
readonly base = `${environment.apiUrl}/v1`;
list(q: PageQuery): Observable<PagedResult<OrderDto>> { return this.http.get<PagedResult<OrderDto>>(`${this.base}/orders`, { params: toParams(q) }); }
```
Client DTOs generated from the spec in CI (`ng-openapi-gen`) so drift is a build failure.

## Manual trace checklist
1. Error interceptor and per-service `catchError`: enumerate the shapes parsed; map each to a server controller.
2. List every endpoint the client calls (grep `this.http.` / `api.get|post|put|delete`) and diff against the server endpoint table: calls to routes that do not exist (stale) and server routes no client uses (candidates for removal in the next version).
3. Client models vs server DTOs: sensitive or internal fields present client-side.
4. Pagination: services that paginate client-side.
5. Version prefix consistency across services and `proxy.conf.json`.
6. Hand-written models: pick the three most-used DTOs in `shared/models` and compare them field by field with the server DTO or spec; record drift (renamed, missing, extra fields) in the endpoint table notes.
7. Dates on the wire: request bodies built with `formatDate(x, 'dd/MM/yyyy', ...)` or `DatePipe` output instead of `toISOString()`; record the format and hand zone correctness to `audit-datetime-and-timezone`.
8. List filters: every filter field a screen sends (`CompanyId`, `BranchId`, `SearchTerm`, date range) exists in the server's list-query DTO; a filter the client sends and the server ignores is silent contract drift.

## Stack-specific false positives
- A single interceptor with one fallback for the framework default (`ProblemDetails` + plain string for network errors).
- Client-side pagination of a small, bounded reference list.
- Generated client folders regenerated in CI (check the pipeline).
- `err.message` used only for `HttpErrorResponse` with `status === 0` (network failure): an Angular shape, not a server shape.
- PascalCase query keys built in one place (a single `buildHttpParams`) that match the .NET model binder exactly: consistent, not drift; still note the casing in the naming row.
- Client models with `companyId`/`branchId` for the user's *own* tenant: expected; the finding is only other tenants' identifiers or secrets.

## Tooling
- Count client-side error parsers per field (each distinct field is one server shape):
  `grep -rn "err\.error\.\(message\|error\|detail\|errors\|title\)" src/app | sort | uniq -c`
- List every endpoint the client calls, then compare with `audit/evidence/audit-api-contract/endpoints.md`:
  `grep -rn "this\.http\.\(get\|post\|put\|patch\|delete\)" src/app | sed 's/.*http\.//' | sort`
- Detect a stale generated client:
  `npx ng-openapi-gen --input swagger.json --output /tmp/client` and diff against the committed client.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py <repo> --patterns scripts/patterns/angular.json` for error-field parsers, sensitive client model fields and client-side paging.

## References
ASVS 13.1, OWASP API Security Top 10 2023 (API9 inventory), RFC 9457. The backend reference for this stack pair owns the server-side findings.
