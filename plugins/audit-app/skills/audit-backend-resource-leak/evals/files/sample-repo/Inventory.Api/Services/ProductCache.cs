using Microsoft.Extensions.Caching.Memory;

namespace Inventory.Api.Services;

public class ProductCache
{
    private readonly IMemoryCache _cache;
    public ProductCache(IMemoryCache cache) => _cache = cache;

    // LEAK (CACHE): no expiration, no Size, cache registered without SizeLimit,
    // and the key is a user-supplied search term - unbounded key space.
    public void Remember(string searchTerm, object result)
    {
        _cache.Set("search:" + searchTerm, result);
    }

    // OK: bounded entry - must NOT be flagged.
    public object? GetOrLoad(int productId, Func<object> load)
    {
        return _cache.GetOrCreate("product:" + productId, entry =>
        {
            entry.SetSize(1).SetSlidingExpiration(TimeSpan.FromMinutes(10));
            return load();
        });
    }
}
