# .NET / ASP.NET Core reference for audit-multi-tenant-isolation

## Stack markers
`*.csproj`, `Program.cs`, EF Core (`Microsoft.EntityFrameworkCore.*`). In this codebase tenant selection is often a static holder (`CustomConnectionString.DbName`) set per request from `_identityService.GetClaimDetail().DbName` - a database-per-tenant hybrid. Also common: shared DB with a `CompanyId`/`BranchId`/`TenantId` column and an EF `HasQueryFilter`.

## Where the relevant code lives
`*DbContext.cs` (`HasQueryFilter`, connection string selection), controllers/managers (queries, writes), `BackgroundJobs/`/Hangfire registrations, `Infrastructure/`/tenant-context services, cache usage (`IDistributedCache`/`IMemoryCache`), file/blob code (`PhysicalFile`, Azure `BlobClient`, Google Drive).

## Dangerous / interesting APIs and patterns
- `IgnoreQueryFilters()` - the single most important grep; it turns off the global tenant filter. Every use must add an explicit `TenantId ==` predicate.
- `FromSqlRaw` / `FromSqlInterpolated` / `ExecuteSqlRaw` - raw SQL is NOT covered by `HasQueryFilter`; the SQL must include the tenant predicate itself.
- Tenant id from input: `dto.TenantId`, `[FromBody]` shapes carrying `TenantId`/`CompanyId`, query string `?companyId=`. Tenant must come from the claim/context.
- Write paths setting `entity.TenantId = dto.TenantId` instead of `= _tenant.TenantId`.
- Background jobs: no `HttpContext`, so a claim-based `ITenantContext` throws or returns nothing; jobs often add `IgnoreQueryFilters()` and then process all tenants unscoped. The static `CustomConnectionString.DbName` must be set explicitly in the job.
- Cache keys: `$"document:{id}"` with no tenant segment - a cross-tenant serve. Use `$"tenant:{_tenant.TenantId}:document:{id}"`.
- Blob/file paths: `/documents/{id}.pdf` with no tenant folder is guessable across tenants.

## What "good" looks like
```csharp
modelBuilder.Entity<Invoice>().HasQueryFilter(i => i.TenantId == _tenant.TenantId);   // global
// raw SQL must carry the predicate:
_db.Invoices.FromSqlInterpolated($"SELECT * FROM Invoices WHERE TenantId = {_tenant.TenantId}");
// write: tenant from context, not body
var inv = new Invoice { TenantId = _tenant.TenantId, Total = dto.Total };
// cache + blob keyed by tenant
var key = $"tenant:{_tenant.TenantId}:invoice:{id}";
var path = $"/blob/{_tenant.TenantId}/documents/{id}.pdf";
// job: set tenant per iteration
foreach (var t in tenantIds) { _tenant.Set(t); Process(); }
```

## Manual trace checklist
1. Every `IgnoreQueryFilters()` and raw SQL - does it add a tenant predicate?
2. Every write - is `TenantId` set from context, never from the DTO?
3. Every background job / Hangfire method - does it set tenant context (or loop tenants) explicitly?
4. Every cache key and blob/file path - tenant segment present?
5. Admin/reporting/export/aggregate paths - these deliberately span tenants; confirm they are authorized and audited.

## Stack-specific false positives
`IgnoreQueryFilters()` immediately followed by `.Where(x => x.TenantId == ...)`; raw SQL with a parameterized `TenantId`; admin endpoints (SuperAdmin) whose job is cross-tenant reporting, provided they are authorized.

## Tooling
`SecurityCodeScan`, custom Roslyn analyzer for `IgnoreQueryFilters`, `scripts/data_access_paths.py` for the inventory, `scripts/tenant_probe.py` for live confirmation.

## References
CWE-284 (improper access control), CWE-639 (IDOR/authorization bypass by key), CWE-524 (cache exposure), CWE-668 (resource exposed to wrong sphere). ASVS 4.1/4.2, 8.1. OWASP A01:2021.
