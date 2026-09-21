# Java / Spring Boot reference for audit-performance-and-scalability

## Stack markers
`pom.xml`/`build.gradle` with `spring-boot-starter-web` (Tomcat, thread-per-request) or `spring-boot-starter-webflux` (Netty, event loop - blocking calls are fatal there). Sub-variants: Spring Cloud Gateway, Resilience4j vs Hystrix, Spring Session, Spring Cache with Caffeine/Redis, `@Async` executors, virtual threads (`spring.threads.virtual.enabled`, JDK 21).

## Where the relevant code lives
`application*.yml` (`server.compression`, `server.tomcat.threads.max`, `spring.datasource.hikari.*`, `spring.session.store-type`, `spring.cache.type`, `resilience4j.*`), `@Configuration` (RestTemplate/WebClient beans, executors, cache managers), `*Service.java` (sequential calls, blocking), `*Controller.java` (payload shapes, inline work), `@Scheduled`/`@Async` classes.

## Dangerous / interesting APIs and patterns
- BLOCK: `.block()`/`.blockFirst()` on `Mono`/`Flux` inside a WebFlux handler; `CompletableFuture.get()`/`.join()` in request threads; `Thread.sleep`; synchronous `RestTemplate` in WebFlux; `synchronized` on hot service methods; `Files.readAllBytes` on large files in handlers.
- SEQ: consecutive `restTemplate.getForObject(...)` / `webClient...block()` / `repo.find...` calls with independent inputs -> `CompletableFuture.supplyAsync` + `allOf`, or `Mono.zip`; loops calling a remote per item.
- CACHE: no `@EnableCaching`; reference data loaded per request; `@Cacheable` with the default `ConcurrentMapCacheManager` (unbounded, no TTL, per-instance); no `@CacheEvict`/`@CachePut` on write paths; no `Cache-Control`/ETag on public GETs (`ShallowEtagHeaderFilter` absent).
- COMPRESS: `server.compression.enabled` missing/false; `mime-types` not including `application/json`; `min-response-size` too high; gateway not compressing.
- PAYLOAD: controllers returning entities (`List<Product>` with `@OneToMany` graphs serialised by Jackson - also N+1); `@JsonIgnore` missing on back-references; `spring.jackson.default-property-inclusion` not `non_null`; byte[] fields in DTOs.
- CHATTY: per-row `GET /x/{id}` endpoints without a batch variant; dashboard endpoints returning one counter each.
- POOL: `spring.datasource.hikari.maximum-pool-size` (default 10) vs `server.tomcat.threads.max` (default 200) - 200 threads waiting on 10 connections shows as p95 spikes; `connection-timeout` (30 s default - too long); WebClient `ConnectionProvider` limits; `@Async` default `SimpleAsyncTaskExecutor` (unbounded threads, no pool).
- TIMEOUT: `new RestTemplate()` without `setConnectTimeout`/`setReadTimeout`; `WebClient.create()` without `responseTimeout`; no `@CircuitBreaker`/`@TimeLimiter`/`@Retry` (Resilience4j) on external clients; Feign without `feign.client.config.default.readTimeout`; JDBC `query-timeout` absent for reports.
- ALLOC: `new ObjectMapper()` per call, `String` concatenation in loops, `Stream.collect` on huge lists, PDF/Excel (POI) generation on the request thread, `Pattern.compile` per call.
- INLINE-BG: email (`JavaMailSender.send`), PDF, report generation, third-party submissions inside the controller; `@Async` on `void` methods as the fix without a bounded executor or error handler.
- STATE: `HttpSession` used with no `spring-session-data-redis`/`jdbc` (`spring.session.store-type` absent -> in-memory, breaks at 2 instances); `static`/singleton caches of tenant data; local filesystem for uploads; `@Scheduled` without ShedLock (runs on every instance); Ehcache/Caffeine holding data that must be coherent.

## What "good" looks like
```yaml
server:
  compression: { enabled: true, mime-types: application/json,text/html,text/css,application/javascript, min-response-size: 1024 }
  tomcat.threads.max: 200
spring:
  datasource.hikari: { maximum-pool-size: 30, connection-timeout: 5000 }
  session.store-type: redis
  cache: { type: redis, redis.time-to-live: 5m }
resilience4j.circuitbreaker.instances.pricing: { failure-rate-threshold: 50, wait-duration-in-open-state: 30s }
resilience4j.timelimiter.instances.pricing.timeout-duration: 2s
```
```java
var cf = CompletableFuture.supplyAsync(() -> customers.get(id), pool);
var pf = CompletableFuture.supplyAsync(() -> pricing.quote(items), pool);
var tf = CompletableFuture.supplyAsync(() -> tax.rate(region), pool);
CompletableFuture.allOf(cf, pf, tf).join();        // one round-trip time, not three

@Cacheable(cacheNames = "products", key = "#companyId + ':' + #page") public Page<ProductDto> list(...)
@CacheEvict(cacheNames = "products", allEntries = true) public Product save(...)
@Bean RestTemplate rt(RestTemplateBuilder b) { return b.setConnectTimeout(Duration.ofSeconds(2)).setReadTimeout(Duration.ofSeconds(5)).build(); }
```

## Manual trace checklist
1. Landing/main list: controller -> service -> repository; awaits/remote calls in series; entity vs DTO returned.
2. Save/checkout: remote calls, inline mail/PDF, transaction length.
3. `application.yml`: compression, session store, cache type + TTL, Hikari vs Tomcat sizing, Resilience4j.
4. Every RestTemplate/WebClient/Feign bean: timeouts, retries, circuit breaker.
5. `@Scheduled` and `@Async`: executor bounded? locks for multi-instance?
6. WebFlux only: any `.block()` in the request path is Critical.

## Stack-specific false positives
- `.block()` in tests or CommandLineRunner startup code.
- Sequential calls where the second uses the first's result.
- `ConcurrentMapCacheManager` in a single-instance internal tool - rate Low with the constraint noted.

## Tooling
- Actuator: `/actuator/metrics/http.server.requests` (percentiles with `management.metrics.distribution.percentiles-histogram.http.server.requests=true`), `hikaricp.connections.pending`, `tomcat.threads.busy`, `jvm.threads.states`.
- `async-profiler` / JFR (`jcmd <pid> JFR.start duration=120s filename=rec.jfr`) during load; `jstack` for threads blocked in `socketRead0` (pool/timeout) or `park` (Hikari wait).
- Static: SonarQube S2142/S2276 (blocking), Error Prone `FutureReturnValueIgnored`; `spring-boot-actuator` `/actuator/caches` to confirm cache managers.

## References
CWE-400, CWE-1050, CWE-1088, CWE-1072; Spring Boot docs "HTTP response compression", "Caching", "Spring Session", "Task Execution and Scheduling"; Resilience4j docs; HikariCP "About Pool Sizing".
