# Java / Spring reference for audit-multi-tenant-isolation

## Stack markers
`pom.xml`/`build.gradle` with Spring + Hibernate/JPA. Tenancy via Hibernate `@Filter`/`@FilterDef`, `AbstractRoutingDataSource` (db-per-tenant), or an explicit `tenantId` column with a base repository.

## Where the relevant code lives
`@Entity` classes (`@Filter`), `*Repository.java` (`@Query`, derived queries), a `TenantContext`/`ThreadLocal` holder, `SecurityConfig`, `@Scheduled`/listener classes, cache config (`@Cacheable`, Redis), file/S3 code.

## Dangerous / interesting APIs and patterns
- `createNativeQuery` / `@Query(nativeQuery=true)` / `entityManager.createQuery` - not covered by Hibernate `@Filter`; must include the tenant predicate.
- `session.disableFilter("tenantFilter")` - turns isolation off.
- Hibernate filters must be enabled per session (an interceptor/aspect); if the enabling code is missing, the `@Filter` never applies - verify it runs.
- Tenant id from `@RequestBody`/`@RequestParam`/header trusted directly.
- `@Scheduled` and `@KafkaListener`/`@RabbitListener` run on threads with no request scope; a `ThreadLocal` TenantContext is empty there.
- `@Cacheable` without the tenant id in `key`; S3/file keys without a tenant prefix.

## What "good" looks like
```java
// enable the filter per request
session.enableFilter("tenantFilter").setParameter("tenantId", TenantContext.get());
// repository derived query scoped by tenant
Optional<Invoice> findByIdAndTenantId(Long id, Long tenantId);
// cache keyed by tenant
@Cacheable(value="invoice", key="#tenant + ':' + #id")
// job: set context per tenant
tenants.forEach(t -> { TenantContext.set(t); process(); TenantContext.clear(); });
```

## Manual trace checklist
1. Confirm the Hibernate filter is actually enabled on every request (interceptor/aspect present).
2. Every native query / disableFilter - tenant predicate present?
3. Writes set tenant from `TenantContext`/security principal, not the body.
4. `@Scheduled`/listeners set and clear `TenantContext` per item.
5. `@Cacheable` keys and object-store keys include the tenant.

## Stack-specific false positives
Native queries with a bound `:tenantId`; `AbstractRoutingDataSource` giving each tenant its own datasource (then a missing column filter is expected); admin reporting endpoints that intentionally span tenants and are authorized.

## Tooling
`find-sec-bugs`, `scripts/data_access_paths.py`, `scripts/tenant_probe.py`.

## References
CWE-284, CWE-639, CWE-524, CWE-668. ASVS 4.1/4.2, 8.1. OWASP A01:2021.
