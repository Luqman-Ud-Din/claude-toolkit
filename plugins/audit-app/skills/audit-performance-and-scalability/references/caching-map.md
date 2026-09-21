# Caching opportunity map - how to fill it

One row per cacheable thing. Every row must have all four columns; a cache
with no invalidation trigger is a bug report waiting to happen, and a cache
with no TTL is a leak (`audit-backend-resource-leak` CACHE class).

| Column | How to decide |
|---|---|
| What | The unit of data, keyed: "product list for companyId+branchId+page", "tax rate by region", "user permissions by userId", "rendered dashboard HTML". Name the key parts - the key space decides the cache size. |
| Where | The layer closest to the consumer that stays correct: browser (HTTP cache headers / client store), CDN/edge (static and public GET), response cache (server-side, per URL+vary), distributed cache (Redis/Memcached - shared across instances, survives deploys), in-process (per instance - only for data that may differ per instance without harm, or very hot and tiny). Multi-instance deployments: in-process caches of tenant data must be coherent or short-lived (<= 60 s). |
| TTL | Short enough that stale data is harmless, long enough to pay off. Reference data: hours-days. Lists users edit: 1-5 min *plus* event invalidation. Per-user: session length. Never "forever". |
| Invalidation trigger | The write path that makes it stale: "product create/update/delete in ProductsController", "role change", "new build (hashed filenames)". Name the code location that must evict or publish. If none exists, the finding's remediation must add it. |
| Expected win | Estimate from the inventory: calls/min x cost per call. Put the arithmetic in. |

## Layers per stack (see references/<stack>.md for API names)
| Layer | .NET | Java/Spring | Node | Python/Django | Frontend |
|---|---|---|---|---|---|
| HTTP cache headers | `[ResponseCache]`, `Cache-Control` via middleware, ETag | `CacheControl`/`ShallowEtagHeaderFilter` | `res.set('Cache-Control')`, `etag` | `@cache_control`, `ConditionalGetMiddleware` | consumed by the browser; SW `ngsw-config` / Workbox |
| Response cache (server) | `AddResponseCaching`/`AddOutputCache` | Spring Cache on controller + `@Cacheable` | `apicache`, Nest `CacheInterceptor` | `@cache_page`, `UpdateCacheMiddleware` | - |
| Distributed | `IDistributedCache` (Redis), `HybridCache` | `RedisCacheManager`, Caffeine+Redis tiered | `ioredis` + `cache-manager` | `django-redis` `CACHES` | - |
| In-process | `IMemoryCache` with SizeLimit | Caffeine `maximumSize` | `lru-cache` with `max`/`ttl` | `LocMemCache` MAX_ENTRIES / `lru_cache(maxsize)` | service-level `shareReplay(1)`, React Query `staleTime`, Pinia store |
| Query/second-level | EF compiled queries; no 2nd-level cache built in | Hibernate L2 (`@Cache`) | Prisma Accelerate / manual | `cachalot`/`cacheops` | - |
| CDN/static | hashed assets, `immutable`, `max-age=31536000` | same | same | `ManifestStaticFilesStorage` | build output hashing already on; verify headers |

## Invalidation patterns
- Event on write: publish `ProductChanged(companyId)` and evict `products:{companyId}:*` (Redis `SCAN`+`DEL` or key versioning: store `products:{companyId}:v` and bump it - O(1) invalidation).
- Version key: cache key includes a version number bumped on write; old entries expire by TTL.
- Write-through: update cache in the same transaction/on commit hook (`transaction.on_commit`, EF `SaveChanges` interceptor).
- TTL-only: acceptable for reference data and for lists where minutes of staleness are OK - say so in the row.
- Multi-tenant: always include tenant id in the key; never cache a tenant-scoped list under a global key (this becomes an `audit-multi-tenant-isolation` finding).

## Things not to cache
- Per-user authorization decisions longer than the token lifetime.
- Stock/balance figures that drive business decisions (or cache with second-level TTL and show "as of").
- Responses with `Set-Cookie` or `Authorization`-dependent bodies at the CDN.
