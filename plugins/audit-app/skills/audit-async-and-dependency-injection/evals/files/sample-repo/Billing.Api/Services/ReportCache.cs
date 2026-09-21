using Billing.Api.Data;
using Microsoft.EntityFrameworkCore;

namespace Billing.Api.Services;

// ASYNC (DI): registered as Singleton in Program.cs, holds a Scoped DbContext for the process lifetime.
public class ReportCache
{
    private readonly BillingDbContext _db;
    private readonly ILogger<ReportCache> _logger;

    public ReportCache(BillingDbContext db, ILogger<ReportCache> logger)
    {
        _db = db;
        _logger = logger;
    }

    public Task<decimal> OutstandingAsync(int companyId, CancellationToken ct)
        => _db.Invoices.Where(i => i.CompanyId == companyId && i.Status == "Open").SumAsync(i => i.Total, ct);
}
