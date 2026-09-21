# .NET / EF Core reference for audit-orm-query-and-data-access

## Stack markers
`*.csproj` referencing `Microsoft.EntityFrameworkCore.*`; Dapper (`Dapper` package) means raw SQL - paging and N+1 rules still apply, tracking does not. Sub-variants: repository/manager layer wrapping `DbSet` (common: `RepositoryBaseManager<T>` with `GetAll()`, `FindByCondition()`), `IQueryable` leaking to controllers, multiple `DbContext`s per physical DB (multi-tenant via connection string swap).

## Where the relevant code lives
`*DbContext.cs` (`OnModelCreating`: `HasIndex`, `HasQueryFilter`, `UseLazyLoadingProxies`), `*Manager.cs` / `*Repository.cs` / `RepositoryBase*.cs`, `Controllers/**` (`GetPaginationList`, `GetAll`, `Export*`), `Extensions/*Pagination*`, `SharedLibrary/PagedList.cs`-style helpers, `BackgroundJobs/` (batch loops).

## Dangerous / interesting APIs and patterns
- NPLUS1: `foreach`/`for`/`.Select(x => _db...)`/`.ForEach(` whose body has `_db.<Set>.` / `_manager.<X>.` / `FirstOrDefault(` / `Find(` / `SingleOrDefault(` / `Where(...).ToList()` / `Any(`; navigation access (`item.Product.Name`) in a loop when `UseLazyLoadingProxies()` is configured; `Include` missing on the parent query; `AutoMapper` `ProjectTo` absent while mapping entities with navigations.
- UNBOUNDED: `.ToList()`, `.ToListAsync()`, `.ToArray()`, `.AsEnumerable()` on a `DbSet` without `Skip(`/`Take(` in the same chain; `GetAll()` / `FindAll()` / `FindByCondition(...)` returning `IEnumerable` consumed in a controller without paging; `PagedList`/`PaginationAssign` called *after* `ToList()` (paging in memory).
- TRACKING: `_db.<Set>.Where(...).ToListAsync()` returned from a `Get*` action with no `AsNoTracking()`; no `ChangeTracker.QueryTrackingBehavior = NoTracking`; `AsNoTracking()` present but result later `Update()`ed (opposite bug).
- INDEX: `Where(x => x.CompanyId == c && x.BranchId == b && x.<Col> ...)`, `OrderBy(x => x.<Col>)`, `Contains(` (LIKE '%x%') on columns not in `HasIndex`/`[Index]`/migration scripts.
- TXN: two `SaveChangesAsync()` in one method/service call; `SaveChanges` in a loop; `_manager.Sale.Create` + `_manager.Stock.Update` + `_manager.Ledger.Create` without `BeginTransactionAsync()` / `TransactionScope` / a single `SaveChanges`; transaction on one context while writes go to another (`_masterManager` vs `_manager`).
- INEFFICIENT: `.Count() > 0`, `.Count() == 0`, `.Count() >= 1` (use `Any()`); `.ToList().Where(`, `.AsEnumerable().Where(`, `.ToList().First(`; `FirstOrDefault(...)` followed by `.<SingleProperty>` (project instead); `Include` of collections that are never read; `string.ToLower()` inside `Where` on non-computed columns; `DateTime.Now` compared inside `Where` per row (fine) vs client-side date formatting inside `Where` (client eval; EF Core 3+ throws, older evaluates client-side); `Select(x => new Dto { Lines = x.Lines.ToList() })` (cartesian explosion - use `AsSplitQuery()`).

## What "good" looks like
```csharp
public async Task<PagedList<ProductDto>> GetPage(int companyId, int branchId, PaginationModel p, CancellationToken ct)
{
    var q = _db.Products.AsNoTracking()
        .Where(x => x.CompanyId == companyId && x.BranchId == branchId && !x.IsDeleted);
    if (!string.IsNullOrEmpty(p.SearchTerm)) q = q.Where(x => x.Name.StartsWith(p.SearchTerm));   // sargable
    var total = await q.CountAsync(ct);
    var items = await q.OrderBy(x => x.Name)
        .Skip((p.PageNumber - 1) * p.PageSize).Take(Math.Min(p.PageSize, 100))
        .Select(x => new ProductDto { Id = x.Id, Name = x.Name, Price = x.SalePrice })      // projection: no tracking, no over-fetch
        .ToListAsync(ct);
    return new PagedList<ProductDto>(items, total, p.PageNumber, p.PageSize);
}

// N+1 fix: batch or Include
var sale = await _db.Sales.Include(s => s.Lines).ThenInclude(l => l.Product).AsSplitQuery().FirstAsync(s => s.Id == id, ct);

// multi-table write: one unit of work
await using var tx = await _db.Database.BeginTransactionAsync(ct);
_db.Sales.Add(sale); _db.StockMovements.AddRange(moves); _db.LedgerEntries.Add(entry);
await _db.SaveChangesAsync(ct); await tx.CommitAsync(ct);

var exists = await _db.Products.AnyAsync(x => x.Sku == sku, ct);     // not Count() > 0
```

## Manual trace checklist
1. Main grid endpoints (`GetPaginationList`, `GetAll`): open the manager method behind them; confirm `Skip/Take` is applied to the `IQueryable`, not to a `List`; confirm `AsNoTracking()` or projection; count `Include`s (each collection Include multiplies rows unless `AsSplitQuery()`).
2. Repository base class: does `GetAll()` return `IQueryable` (fine) or `IEnumerable`/`List` (every caller is unbounded and tracked)? One finding on the base with all callers listed.
3. Sale/purchase/invoice save paths: enumerate tables written, find the transaction boundary; check both `_manager` and `_masterManager` contexts if writes span physical DBs (distributed - flag as TXN with "cannot be atomic; needs outbox/compensation").
4. Reports and Excel exports (EPPlus): `ToListAsync()` on the full range with no `Take` - decide whether streaming (`AsAsyncEnumerable()`) or a row cap is the fix.
5. Loops in background jobs: `SaveChanges` per iteration (fine for batching, but N+1 on reads inside is not).
6. Every `Where`/`OrderBy` column set on the top 10 endpoints -> `audit-db-schema` index list (`HasIndex` in `OnModelCreating`, `[Index]` attributes, or SQL scripts).

## Stack-specific false positives
- `ToList()` on a query that already has `Take(` earlier in the chain, or on reference tables (`Currencies`, `Units`, `Roles`) - bounded.
- `Count()` used to return a total for paging - correct; only `Count() > 0` comparisons are the smell.
- Loops that call the DB but are bounded by design (per-branch loop over < 20 branches) - note the bound, rate Low or false-positive.
- Tracking on a read that is immediately updated in the same method - required.
- Two `SaveChanges` inside one explicit transaction - fine (needed to get generated ids).

## Tooling
- Query logging: `references/query-logging.md` (EF Core block); `.TagWith("...")` to label suspect queries.
- `dotnet-counters monitor -p <pid> --counters Microsoft.EntityFrameworkCore` (queries-per-second, active contexts).
- Roslyn: `Microsoft.EntityFrameworkCore.Analyzers` (ships with EF), `EF1001`; `Meziantou.Analyzer` MA0020/MA0031 (`Count() > 0`); `ErikEJ.EFCorePowerTools` for model diagrams and unused Includes.
- SQL side: `SET STATISTICS IO ON` / Query Store top resource-consuming queries to confirm estimated row counts.

## References
CWE-1049, CWE-770, CWE-400, CWE-662; ASVS-12.1.1; EF Core docs "Efficient Querying", "Loading Related Data - Split queries", "Tracking vs No-Tracking", "Logging, events, and diagnostics".
