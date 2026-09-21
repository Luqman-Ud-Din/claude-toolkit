using System;
using System.Collections.Generic;
using Microsoft.AspNetCore.Http;
using System.Threading.Tasks;

namespace Ledger.Api.Infrastructure
{
    // ISSUE (shared static map mutated per request): Dictionary is not thread-safe.
    // Concurrent requests corrupt it (lost counts, InvalidOperationException, or an
    // infinite loop inside the dictionary), and the counts are per process anyway.
    public class RateLimiterMiddleware
    {
        private static Dictionary<string, int> _hits = new Dictionary<string, int>();
        private readonly RequestDelegate _next;

        public RateLimiterMiddleware(RequestDelegate next)
        {
            _next = next;
        }

        public async Task InvokeAsync(HttpContext context)
        {
            var key = context.Connection.RemoteIpAddress?.ToString() ?? "unknown";
            if (!_hits.ContainsKey(key))
            {
                _hits[key] = 0;
            }
            _hits[key]++;
            if (_hits[key] > 100)
            {
                context.Response.StatusCode = 429;
                return;
            }
            await _next(context);
        }
    }
}
