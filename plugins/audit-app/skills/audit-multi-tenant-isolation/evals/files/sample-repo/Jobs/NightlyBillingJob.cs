using Microsoft.EntityFrameworkCore;
using Saas.Api.Data;

namespace Saas.Api.Jobs;

// Planted #3: background job runs with NO tenant context. The global query filter
// depends on ITenantContext, which has no HttpContext here, so this either throws
// or (with IgnoreQueryFilters) processes every tenant's data in one pass with no
// per-tenant scoping or audit.
public class NightlyBillingJob
{
    private readonly AppDbContext _db;
    public NightlyBillingJob(AppDbContext db) => _db = db;

    // Invoked by Hangfire on a schedule; there is no authenticated user or tenant claim.
    public void Run()
    {
        var invoices = _db.Invoices.IgnoreQueryFilters().ToList(); // all tenants, unscoped
        foreach (var inv in invoices)
        {
            inv.Total *= 1.0m; // recompute
        }
        _db.SaveChanges();
    }
}
