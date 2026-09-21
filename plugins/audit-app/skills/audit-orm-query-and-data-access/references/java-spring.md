# Java / Spring (Hibernate, JPA, Spring Data) reference for audit-orm-query-and-data-access

## Stack markers
`pom.xml`/`build.gradle` with `spring-boot-starter-data-jpa` (Hibernate), `spring-boot-starter-data-jdbc`, `jooq`, `mybatis`, or `spring-boot-starter-data-mongodb`. Sub-variants: Spring Data repositories (derived queries, `@Query`), `EntityManager`/Criteria API, JOOQ (typed SQL - paging rules apply, tracking N/A), MyBatis (XML mappers - N+1 via nested `<select>`).

## Where the relevant code lives
`*Repository.java` (Spring Data interfaces: method names encode the query), `*Service.java` (`@Transactional` boundaries, loops), `*Controller.java` (`Pageable` parameters), entity classes (`@OneToMany(fetch = ...)`, `@BatchSize`, `@Index`/`@Table(indexes=)`), `application*.yml` (`spring.jpa.open-in-view`, `hibernate.default_batch_fetch_size`).

## Dangerous / interesting APIs and patterns
- NPLUS1: `for (X x : list) { repo.findById(...) }` / `.stream().map(x -> repo.find...)`; accessing a lazy collection (`order.getLines().size()`) inside a loop over parents; `@OneToMany` default LAZY iterated after the query with no `JOIN FETCH`/`@EntityGraph`/`@BatchSize`; `spring.jpa.open-in-view: true` (default!) masks lazy loading in controllers/serializers - Jackson serialising an entity triggers a query per lazy association.
- UNBOUNDED: `findAll()` with no `Pageable`/`Sort` returned from a controller; `@Query("select e from E e")` returning `List` with no `Pageable` parameter; `getResultList()` with no `setMaxResults`; JOOQ `fetch()` with no `limit()`; `findBy...` derived queries returning `List` from large tables.
- TRACKING (persistence-context growth): read-only service methods without `@Transactional(readOnly = true)`; entity results where a DTO projection (interface/record projection, `select new ...`) would do; batch loops without `entityManager.clear()`/`flush()` every N rows.
- INDEX: derived queries `findByCompanyIdAndStatusOrderByCreatedAt(...)` where `@Table(indexes = ...)` / Flyway/Liquibase scripts have no matching index; `like %:term%` (leading wildcard).
- TXN: `save()` on two repositories in one service method without `@Transactional`; `@Transactional` on a private/self-invoked method (proxy bypass - no transaction); `@Transactional` on a controller (too wide) or missing on the service; `saveAll` in a loop with `@Transactional(propagation = REQUIRES_NEW)` per item.
- INEFFICIENT: `count() > 0` / `findAll().size()` / `!findAll().isEmpty()` (use `existsBy...`); `findAll().stream().filter(...)` (filter in Java); `@ManyToOne(fetch = EAGER)` on hot entities; `Collection` results converted with `new ArrayList<>(...)`; `Cascade.ALL` on large graphs; missing `@BatchSize`; `select *` via entity load when one column is needed.

## What "good" looks like
```java
public interface ProductRepository extends JpaRepository<Product, Long> {
    Page<ProductSummary> findByCompanyIdAndDeletedFalse(Long companyId, Pageable pageable);   // projection + paging
    boolean existsBySku(String sku);                                                          // not count() > 0
    @EntityGraph(attributePaths = {"lines", "lines.product"})
    Optional<Sale> findWithLinesById(Long id);                                                // no N+1
}

@Service
public class SaleService {
    @Transactional                                     // one transaction for sale + stock + ledger
    public Sale post(SaleRequest req) { ... saleRepo.save(sale); stockRepo.saveAll(moves); ledgerRepo.save(entry); ... }

    @Transactional(readOnly = true)
    public Page<ProductSummary> list(Long companyId, Pageable p) { return repo.findByCompanyIdAndDeletedFalse(companyId, capped(p, 100)); }
}
```
`spring.jpa.open-in-view: false`, `spring.jpa.properties.hibernate.default_batch_fetch_size: 50`.

## Manual trace checklist
1. Controllers returning `List<Entity>`: which ones lack `Pageable`? For each, entity growth class (transactional vs reference).
2. `open-in-view` setting: if true, every serialised entity with lazy associations is an N+1 in the JSON layer; confirm with `org.hibernate.SQL` logging on one detail endpoint.
3. Service methods that call two repositories: `@Transactional` present, public, called through the proxy (not `this.`)?
4. Loops in services and batch jobs over repository calls; look for `@EntityGraph`, `JOIN FETCH`, `@BatchSize`, or `IN` batching.
5. Derived query names -> filter columns -> index list from `audit-db-schema` (Flyway/Liquibase migrations, `@Table(indexes=)`).
6. Reports: `getResultList()` sizes; `Stream<T>` with `@QueryHints(HINT_FETCH_SIZE)` for exports.

## Stack-specific false positives
- `findAll()` on reference/enum-like tables (bounded).
- `count()` used to fill `Page.totalElements` - correct.
- Loops over a small in-memory collection followed by one `saveAll` - not N+1 on the write side (Hibernate batches with `hibernate.jdbc.batch_size`).
- `@Transactional` on a class - applies to all public methods; do not flag methods individually.

## Tooling
- Logging block in `references/query-logging.md` (`org.hibernate.SQL`, `generate_statistics`).
- `datasource-proxy` / `p6spy` with `QueryCountHolder` to assert counts per test; `Hypersistence Optimizer` (commercial) flags N+1 and missing batch sizes; `jpa-buddy`/`JPA Inspector` IDE plugins.
- `spring.jpa.properties.hibernate.query.fail_on_pagination_over_collection_fetch=true` - fails queries that page in memory after a collection fetch.
- SonarQube rules S6857 (`@Transactional` on non-public), S6809 (self-invocation).

## References
CWE-1049, CWE-770, CWE-662; ASVS-12.1.1; Hibernate docs "Fetching", "Batch fetching"; Spring Data JPA "Paging and Sorting", "Projections"; Vlad Mihalcea "N+1 query problem", "open-in-view anti-pattern".
