using System.Collections.Concurrent;
using System.Collections.Generic;

namespace Ledger.Api.Infrastructure
{
    // Negative case: static state that is safe. An immutable, read-only map built
    // once at startup, and a ConcurrentDictionary with atomic AddOrUpdate for the
    // per-process counter.
    public static class SettingsCache
    {
        public static readonly IReadOnlyDictionary<string, string> Defaults =
            new Dictionary<string, string> { ["currency"] = "PKR", ["locale"] = "en-PK" };

        private static readonly ConcurrentDictionary<string, int> _requestCounts = new();

        public static int Count(string route) => _requestCounts.AddOrUpdate(route, 1, (_, v) => v + 1);
    }
}
