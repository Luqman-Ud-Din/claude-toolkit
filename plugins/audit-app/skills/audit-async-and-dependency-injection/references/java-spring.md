# Java / Spring reference for audit-async-and-dependency-injection

## Stack markers
`pom.xml`/`build.gradle` with `spring-boot-starter-*`. Container: Spring (singleton by default). Sub-variants: Spring MVC (Tomcat threads - blocking is starvation) vs WebFlux (Netty event loop - blocking is a deadlock/outage); `@Async` with `@EnableAsync`; Spring Cloud OpenFeign; Quartz; virtual threads on JDK 21 (`spring.threads.virtual.enabled=true` makes BLOCK much cheaper but not free).

## Where the relevant code lives
`@Configuration` classes (`@Bean`, `@Scope`, executors, `RestTemplate`/`WebClient` beans), `@Service`/`@Component`/`@Repository`/`@Controller` classes (constructor injection, `@Autowired` fields), `@Async`/`@Scheduled` classes, `application*.yml` (`spring.task.execution.*`, `feign.client.config.*`, `spring.threads.virtual.enabled`), WebFlux handlers/routers.

## Dangerous / interesting APIs and patterns
- BLOCK: `Mono/Flux.block()`, `.blockFirst()`, `.blockLast()`, `.toFuture().get()`, `CompletableFuture.get()/join()`, `Future.get()`, `Thread.sleep`, `CountDownLatch.await` on request threads; `synchronized` methods on singleton services; `RestTemplate` (blocking) used inside WebFlux; `@Transactional` methods that call remote services (holds a DB connection while waiting on HTTP - pool starvation).
- VOID: `@Async public void ...` (exceptions go to `AsyncUncaughtExceptionHandler` - default only logs, and only if `AsyncConfigurer` is implemented); `@Async` on a method returning a value called without using the `Future`; `Mono`/`Flux` created and never subscribed (nothing runs); `.subscribe()` with no error consumer.
- CANCEL: WebFlux handlers ignoring cancellation (`doOnCancel`); MVC `DeferredResult`/`Callable` without `onTimeout`; long JDBC queries without `queryTimeout`; `@Async` tasks with no interruption handling (`Thread.currentThread().isInterrupted()`); executor `shutdownNow` never called on context close (`@PreDestroy`).
- FIRE: `CompletableFuture.runAsync(...)` result discarded; `executor.submit(...)` result discarded (exceptions swallowed inside the `Future`); `new Thread(...).start()`; `@Async` on `void` for business-critical work (lost on restart); `Flux.subscribe()` fire-and-forget in a request.
- HTTP: `new RestTemplate()` per call/per class field without a builder; `WebClient.create()` per call; `HttpClients.createDefault()` per call; `new OkHttpClient()` per call (each has its own pool and threads); `URL.openConnection()` in loops; Feign clients built with `Feign.builder()` per call.
- TIMEOUT: `new RestTemplate()` (infinite); `RestTemplateBuilder` without `setConnectTimeout`/`setReadTimeout`; `WebClient` without `HttpClient.create().responseTimeout(...)`; Feign without `feign.client.config.default.connectTimeout/readTimeout`; `@Async` without `@TimeLimiter`; JDBC without `spring.datasource.hikari.connection-timeout` reasonable value.
- DI: singleton (`@Service` etc.) constructor/field injecting a `@Scope("prototype")`, `@RequestScope`, `@SessionScope` bean without `proxyMode = ScopedProxyMode.TARGET_CLASS` or `ObjectProvider<T>`/`Provider<T>` (captive - the same prototype/request instance forever); `@Autowired` field injection (hides dependencies; makes captive deps harder to see); `@Transactional`/`@Async`/`@Cacheable` on `private`/`final` methods or self-invoked (`this.method()`) - proxy bypass, annotation silently ignored; `@Bean` methods called directly from other `@Bean` methods in a non-`@Configuration` class (`proxyBeanMethods=false`) - new instances; `static` fields holding beans; `ApplicationContext.getBean()` in services (service locator); circular constructor dependencies "fixed" with `@Lazy`; `@Component` with mutable instance fields written per request (singleton shared state - also a race).

## What "good" looks like
```java
@Service
public class InvoiceService {
    private final FbrClient fbr;                       // singleton -> singleton
    private final ObjectProvider<RequestContext> ctx;  // request-scoped resolved per call, not captured
    public InvoiceService(FbrClient fbr, ObjectProvider<RequestContext> ctx) { this.fbr = fbr; this.ctx = ctx; }

    public InvoiceResult submit(Invoice inv) { var tenant = ctx.getObject().tenantId(); return fbr.submit(inv, tenant); }
}

@Configuration
public class HttpConfig {
    @Bean RestTemplate restTemplate(RestTemplateBuilder b) {
        return b.setConnectTimeout(Duration.ofSeconds(2)).setReadTimeout(Duration.ofSeconds(5)).build();   // one shared instance, timeouts set
    }
    @Bean WebClient webClient() {
        return WebClient.builder().clientConnector(new ReactorClientHttpConnector(HttpClient.create().responseTimeout(Duration.ofSeconds(5)))).build();
    }
    @Bean(name = "jobExecutor") ThreadPoolTaskExecutor jobExecutor() { var e = new ThreadPoolTaskExecutor(); e.setCorePoolSize(4); e.setMaxPoolSize(8); e.setQueueCapacity(100); return e; }
}

@Configuration @EnableAsync
public class AsyncConfig implements AsyncConfigurer {
    @Override public AsyncUncaughtExceptionHandler getAsyncUncaughtExceptionHandler() { return (ex, m, params) -> log.error("async {} failed", m.getName(), ex); }
}

@Async("jobExecutor") public CompletableFuture<Void> notify(Long id) { ... }   // caller can observe failure
```
WebFlux: never `.block()`; compose with `flatMap`/`zip`; blocking libraries wrapped in `Mono.fromCallable(...).subscribeOn(Schedulers.boundedElastic())`.

## Manual trace checklist
1. `di_lifetimes.py` MISMATCH rows: singleton fields typed as request/prototype beans - captive unless `ObjectProvider`/proxy. Request-scoped `TenantContext` captured by a singleton in a multi-tenant app = Critical.
2. Every `@Transactional`/`@Async`/`@Cacheable`: public? Invoked through the proxy (from another bean)? A `private` or `this.`-called one is a silent no-op.
3. WebFlux: grep `.block(` across `src/main` - any hit on a request path is Critical.
4. `@Async void` methods: `AsyncConfigurer` with an exception handler present? Business-critical work in them?
5. HTTP clients: one bean per upstream, timeouts set, Resilience4j/Feign config present.
6. `@Transactional` methods calling remote services: connection held during HTTP - restructure or shorten.
7. Executors: bounded (`ThreadPoolTaskExecutor` with queue capacity and rejection policy)? `@PreDestroy` shutdown?

## Stack-specific false positives
- `.block()` in tests, `CommandLineRunner`, or startup warm-up.
- `@Async` on methods returning `CompletableFuture` whose result is joined by the caller.
- `new RestTemplate()` inside a `@Bean` method body (that is the single shared instance).
- `@Autowired` on constructor (fine) vs fields (smell only).
- `@Lazy` used deliberately to break a cycle that has been documented.

## Tooling
- Static: SonarQube S2142 (interrupted exception), S6809 (`@Transactional` self-invocation), S6813 (field injection), S2226 (servlet fields); Error Prone `FutureReturnValueIgnored`; SpotBugs `RV_RETURN_VALUE_IGNORED_BAD_PRACTICE`; BlockHound (`io.projectreactor.tools:blockhound`) in tests for WebFlux - throws on any blocking call on a non-blocking thread.
- Runtime: `jstack <pid>` during load - threads in `WAITING (parking)` on `CompletableFuture.get`/`FutureTask.get` or `BLOCKED` on a monitor = BLOCK; Actuator `tomcat.threads.busy` at max with low CPU; `hikaricp.connections.pending` > 0 with `@Transactional` + HTTP = held connections.
- `spring.main.lazy-initialization=false` (default) plus a context-load test catches missing beans; there is no built-in captive-dependency validation - rely on `di_lifetimes.py` and review.

## References
CWE-833, CWE-400, CWE-390, CWE-1088, CWE-362; Spring Framework docs "Bean Scopes - Scoped Beans as Dependencies", "Task Execution and Scheduling - @Async exception handling", "Transaction Management - Method visibility and @Transactional"; Project Reactor "Which operator do I need? / blocking"; Resilience4j docs.
