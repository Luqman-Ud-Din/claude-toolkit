# Java / Spring reference for audit-backend-resource-leak

## Stack markers
`pom.xml` / `build.gradle(.kts)` with `spring-boot-starter-*`. Sub-variants: Spring MVC (servlet, thread-per-request) vs WebFlux (reactive; leaks are unreleased `DataBuffer`s and unsubscribed `Flux`); Hibernate/JPA vs JDBC/jOOQ; `@Scheduled` vs Quartz vs Spring Batch.

## Where the relevant code lives
`@Configuration` classes (`@Bean` singletons), `@Service`/`@Component` (singleton by default - every instance field is process-lifetime state), `@Scheduled` methods, `@Async` methods, `@EventListener`, `*Repository`, `application.yml` (`spring.cache.*`, `spring.datasource.hikari.*`), `static` fields anywhere.

## Dangerous / interesting APIs and patterns
- Disposal: `new FileInputStream/FileOutputStream/BufferedReader/FileReader`, `Files.lines(`, `Files.newDirectoryStream(`, `Files.walk(` without try-with-resources; `dataSource.getConnection()`, `Statement`, `ResultSet` not closed; `entityManagerFactory.createEntityManager()` never `close()`d; `HttpURLConnection` without `disconnect()`; OkHttp `Response` body not closed; Apache `CloseableHttpResponse` not closed; `new RestTemplate()` per call; `WebClient.create()` per call; `ExecutorService` created per request without `shutdown()`; `new Timer()` per request; `ZipInputStream`, `Workbook` (POI) not closed.
- Growth: `static List/Map/Set` or singleton-bean fields with `add`/`put` and no `remove`/`clear`; `ConcurrentHashMap` used as a session registry; `ThreadLocal.set` without `remove()` in a pooled thread (Tomcat/executor threads live forever, so the value leaks per thread and per redeploy).
- Cache: `@Cacheable` with the default `ConcurrentMapCacheManager` (unbounded, no TTL); Caffeine without `maximumSize`/`expireAfterWrite`; Ehcache without `heap` entries; hand-rolled `HashMap` caches; `spring.cache.caffeine.spec` missing `maximumSize`.
- Subscriptions: listeners registered via `addListener`/`register(this)` on a singleton bus (Guava `EventBus`, `ApplicationEventMulticaster`) from request-scoped or prototype objects; `Flux.subscribe()` with no `Disposable` kept; `Sinks.many()` with unbounded replay.
- Hot-path allocation: `new byte[large]` per request, `String` concatenation in loops, `ObjectMapper` created per call (`new ObjectMapper()`), `Pattern.compile` per call, `SimpleDateFormat` per call, `StringBuilder` unbounded in a static.
- Background workers: `@Scheduled` methods with `catch (Exception e) {}`; `while (true)` loops in `@PostConstruct`; `@Async` void methods (exceptions silently dropped unless `AsyncUncaughtExceptionHandler` is configured); Spring Batch steps accumulating in a `List` field.

## What "good" looks like
```java
try (var in = Files.newInputStream(path); var reader = new BufferedReader(new InputStreamReader(in))) { ... }

@Bean
public CacheManager cacheManager() {
    var manager = new CaffeineCacheManager("products");
    manager.setCaffeine(Caffeine.newBuilder().maximumSize(10_000).expireAfterWrite(Duration.ofMinutes(10)));
    return manager;
}

@Scheduled(fixedDelay = 30_000)
public void sync() {
    try { doSync(); }
    catch (Exception e) { log.error("sync failed", e); }   // logged, state reset inside doSync
}

@Bean RestTemplate restTemplate(RestTemplateBuilder b) { return b.setConnectTimeout(...).setReadTimeout(...).build(); }  // one shared instance
```
`ThreadLocal` values cleared in a `finally` or a `HandlerInterceptor.afterCompletion`.

## Manual trace checklist
1. Every singleton bean (`@Service`, `@Component`, `@Bean` without scope) with a mutable collection field: who removes entries?
2. Every `@Scheduled` / Quartz job / `@Async`: exception handling present and logged; per-iteration state discarded; `EntityManager` cleared (`em.clear()`) in long batch loops.
3. Every JDBC/JPA access outside Spring Data (`JdbcTemplate` is safe; raw `Connection` is not): closed in try-with-resources?
4. HTTP clients: one shared `RestTemplate`/`WebClient`/OkHttp client bean; per-call `Response.close()` (OkHttp) or `.bodyToMono` consumed (WebClient - an unconsumed body leaks the connection).
5. `ThreadLocal` usage (`RequestContextHolder` is managed; custom ones are not): `remove()` on every exit path?
6. `@Cacheable` names -> which `CacheManager`? If `ConcurrentMapCacheManager` (the default with no cache library on the classpath), every cached method is unbounded.
7. Hikari: `maximumPoolSize`, `leakDetectionThreshold` (set to 30000 during the load test; it logs the stack of any connection held > 30 s).

## Stack-specific false positives
- `JdbcTemplate`, `NamedParameterJdbcTemplate`, Spring Data repositories - they close resources internally.
- `RestTemplate`/`WebClient` built once in a `@Bean` and injected.
- `static final` immutable maps (`Map.of`, `Collections.unmodifiableMap` at init).
- `@Async` methods returning `CompletableFuture` whose result is awaited by the caller - errors propagate.
- `ThreadLocal` managed by a framework interceptor that removes it (`RequestContextHolder`, `SecurityContextHolder`, `TransactionSynchronizationManager`).

## Tooling
- `jcmd <pid> GC.heap_info` every 15 s; `jcmd <pid> GC.class_histogram | head -30` before and after steady state (diff instance counts).
- `jstat -gc <pid> 15000` (columns `OU` old-gen used, `FGC` full GC count); `jcmd <pid> GC.run` to force a GC before the final sample.
- `jcmd <pid> VM.native_memory summary` (needs `-XX:NativeMemoryTracking=summary`) for off-heap growth; `lsof -p <pid> | wc -l` for FDs; `jcmd <pid> Thread.print | grep -c 'tid='` for threads.
- Heap dump: `jcmd <pid> GC.heap_dump /tmp/h.hprof`, analyse with Eclipse MAT "Leak Suspects".
- Hikari `spring.datasource.hikari.leak-detection-threshold=30000` during the test.
- Static analysis: SpotBugs `OBL_UNSATISFIED_OBLIGATION`, `ODR_OPEN_DATABASE_RESOURCE`; Error Prone `StreamResourceLeak`; SonarQube S2095.

## References
CWE-401, CWE-404, CWE-772, CWE-770, CWE-390; Spring docs "Task Execution and Scheduling", "Cache Abstraction" (note on `ConcurrentMapCacheManager`), HikariCP "leakDetectionThreshold"; Eclipse MAT Leak Suspects report.
