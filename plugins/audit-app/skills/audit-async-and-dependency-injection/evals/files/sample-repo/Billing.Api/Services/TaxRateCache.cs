using Billing.Api.Data;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Caching.Memory;

namespace Billing.Api.Services;

public interface ITaxRateCache { Task<decimal> GetAsync(string region, CancellationToken ct); }

// OK: singleton that depends only on singletons and creates a scope per operation - must NOT be flagged.
public class TaxRateCache : ITaxRateCache
{
    private readonly IServiceScopeFactory _scopes;
    private readonly IMemoryCache _cache;

    public TaxRateCache(IServiceScopeFactory scopes, IMemoryCache cache)
    {
        _scopes = scopes;
        _cache = cache;
    }

    public async Task<decimal> GetAsync(string region, CancellationToken ct)
    {
        if (_cache.TryGetValue(region, out decimal rate)) return rate;
        using var scope = _scopes.CreateScope();
        var db = scope.ServiceProvider.GetRequiredService<BillingDbContext>();
        rate = await db.TaxRates.Where(t => t.Region == region).Select(t => t.Rate).FirstAsync(ct);
        _cache.Set(region, rate, new MemoryCacheEntryOptions { Size = 1, AbsoluteExpirationRelativeToNow = TimeSpan.FromHours(1) });
        return rate;
    }
}
