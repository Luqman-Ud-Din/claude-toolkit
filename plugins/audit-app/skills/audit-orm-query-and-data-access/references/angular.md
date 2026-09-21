# Angular reference for audit-orm-query-and-data-access

This skill audits the backend's data access. The frontend matters in two ways:
it defines which list endpoints are hot (page-load calls, grids, dashboards)
and it either sends paging parameters or silently asks for everything. Use this
file to build the endpoint inventory the backend trace starts from, then hand
client-side concerns to `audit-performance-and-scalability` and
`audit-frontend-best-practices`.

## Stack markers
`package.json` with `@angular/core`; `angular.json`; Ionic/Capacitor wrappers (mobile clients often request full lists to filter offline - a backend unbounded endpoint is then "by design", which still needs a cap).

## Where the relevant code lives
`core/services/api.service.ts` (the HTTP entry point and its query-param builder - e.g. `buildHttpParams` translating `PaginationInterface` to `PageNumber`/`PageSize`/`SearchTerm`), `shared/models/pagination*.ts`, feature services (`features/*/services/*.service.ts`), grid/table components (`ag-grid`, `mat-table`, `ion-infinite-scroll`), resolvers (`*.resolver.ts` - run on every navigation), dashboard components (`ngOnInit` fan-out).

## What to inventory (feeds the backend trace)
- Every service method that calls a list endpoint: does it pass `PageNumber`/`PageSize` (or `skip`/`take`, `page`/`limit`)? If not, the backend endpoint is unbounded *and* the client expects it to be - record both.
- Endpoints hit in `ngOnInit`/resolvers of the landing route and the dashboard: these are the "hot list endpoints" the backend checklist step 3(a) starts with.
- Typeahead/search inputs: debounce + `SearchTerm` -> backend `Contains`/`LIKE` on which column (index cross-check input).
- Dropdown/lookup services (`getAllCategories()`, `getAllCustomers()`) - full-table lists the frontend caches; acceptable for reference data, not for customers/products in a multi-tenant SaaS.
- Export buttons: which endpoint, any date-range/row cap sent?

## Client-side signs that the backend is unbounded or over-fetching
- `filter()`/`slice()` on the array returned by the API inside a component (paging done in the browser).
- `MatTableDataSource` fed with the whole response and `MatPaginator` attached client-side.
- Response DTOs with nested collections the template never renders (over-fetch/Include of unused relations).
- Multiple calls to the same list endpoint with different filters on one page (chatty - hand to performance skill).

## What "good" looks like
```ts
// service passes server-side paging; component never slices the array
list(p: PaginationInterface) { return this.api.post<PagedList<Product>>('productapi/Product/GetPaginationList', p); }
// grid: (page)="load({ pageNumber: $event.pageIndex + 1, pageSize: $event.pageSize })"
```

## Manual trace checklist (for the endpoint inventory)
1. Grep feature services for list calls; tabulate endpoint, paging params sent, page it is used on.
2. Open the landing route + dashboard components; list the endpoints called on init.
3. Note search inputs and their backend column.
4. Hand the table to the backend trace (step 3a) and to `audit-performance-and-scalability` (chatty API section).

## Stack-specific false positives
- Client-side slicing of a small reference list fetched once and cached - fine.
- `getAll*` for enums/units/currencies - bounded.

## Tooling
DevTools Network tab filtered to XHR on the landing route (count, size, duration per list call); `ng build --stats-json` is not needed here.

## Hand-off
Bundle, render, over-fetch on the client: `audit-frontend-best-practices`; chatty APIs and caching: `audit-performance-and-scalability`; contract shape (`PagedList` DTO, max page size): `audit-api-contract`.

## References
CWE-770, CWE-400; Angular docs "HttpClient", "Route resolvers"; Material `MatPaginator` server-side example.
