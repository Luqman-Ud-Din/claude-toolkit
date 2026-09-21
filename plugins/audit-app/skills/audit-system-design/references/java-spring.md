# Java / Spring reference for audit-system-design

## Stack markers
`pom.xml` (multi-module `<modules>`), `build.gradle(.kts)` + `settings.gradle` (`include`), `@SpringBootApplication`. Variants: single Boot app; multi-module Maven/Gradle monolith; several Boot apps behind Spring Cloud Gateway/Zuul/Nginx; Spring Cloud (Eureka, Config Server, Sleuth); messaging via Spring AMQP, Spring Kafka, JMS, Spring Cloud Stream; Resilience4j/Hystrix for resilience; Quartz/`@Scheduled` for jobs.

## Where the architecture is visible
- Root `pom.xml`/`settings.gradle`: module list; each module's dependencies on siblings = the build-unit graph (`module_graph.py`). Names reveal layers: `*-web`/`*-api`/`*-rest`, `*-service`/`*-application`, `*-domain`/`*-core`, `*-persistence`/`*-infrastructure`/`*-jpa`, `*-common`/`*-shared`.
- `@SpringBootApplication` classes: one per runtime service. `@EnableScheduling`, `@EnableAsync`, `@EnableFeignClients`, `@EnableDiscoveryClient` show responsibilities.
- `application*.yml`: `spring.datasource.*` (one DB per service or shared?), `spring.rabbitmq.*`/`spring.kafka.*` (brokers), `spring.redis.*`/`spring.cache.type`, `spring.session.store-type`, `spring.cloud.gateway.routes` (service map + where auth filters run), `feign.client.config.*` and `resilience4j.*` (timeouts, retries, breakers), external base URLs.
- `@FeignClient`, `RestTemplate`, `WebClient` beans - outbound edges. `@RabbitListener`, `@KafkaListener`, `@JmsListener`, `@StreamListener` - inbound async edges.
- `SecurityFilterChain`/`WebSecurityConfigurerAdapter` - where authn/authz is enforced; `permitAll()` on internal paths.
- `docker-compose*.yml`, `k8s/`, Helm charts - runtime units and replicas.

## Design smells to grep (mirrored in `scripts/patterns/java-spring.json`)
- Module cycles (`module_graph.py`); `*-domain` depending on `spring-boot-starter-data-jpa`/`web` (infrastructure in domain); `@Entity` classes in the `web` module; `@Repository` injected into `@RestController`.
- `static` mutable fields (`private static Map<...>`, `static ThreadLocal` for tenant without cleanup), `@Component` with mutable instance fields (singleton scope = shared across requests).
- `new RestTemplate()` per call, `RestTemplate` without `setConnectTimeout/ReadTimeout`, `WebClient` without `.timeout()`/`responseTimeout`, Feign without `connectTimeout/readTimeout`.
- No `@Retry`/`@CircuitBreaker`/`@Bulkhead` (Resilience4j) on external calls; `Thread.sleep` retry loops; `catch (Exception e) { log... }` swallowing external failures.
- `ConcurrentHashMap`/Guava `Cache`/`@Cacheable` with the default simple cache as shared state; `spring.session.store-type` absent while `HttpSession` is used; WebSocket/STOMP `enableSimpleBroker` without a relay.
- Two modules/services with `@Entity` mapping the same `@Table(name=...)`; `@Transactional` methods that call REST/queue publishers inside (dual write); `rabbitTemplate.convertAndSend` in a request handler without an outbox.
- `@Scheduled` in every instance without ShedLock/Quartz clustering.
- `synchronized` on hot paths, `CompletableFuture.join()`/`.get()` without timeout in request threads (thread-pool starvation).
- Local filesystem writes (`new FileOutputStream("uploads/")`).
- `permitAll()` on `/internal/**`, `/actuator/**` exposed; `management.server.port` same as app port; service ports published in compose bypassing the gateway.
- God classes: `*Utils`, `*Helper`, `CommonService` with thousands of lines.

## What "good" looks like
```java
@Configuration class HttpConfig {
  @Bean RestClient fbrClient(RestClient.Builder b) {
    return b.baseUrl(props.fbrBaseUrl()).requestFactory(factoryWithTimeouts(2_000, 10_000)).build();
  }
}
@Service class FbrService {
  @CircuitBreaker(name = "fbr", fallbackMethod = "queueForLater")
  @Retry(name = "fbr") @TimeLimiter(name = "fbr")
  public InvoiceAck submit(Invoice i) { ... }
}
// outbox: write event row in the same @Transactional method; a scheduled relay publishes
// tenancy: request-scoped TenantContext bean + AbstractRoutingDataSource, cleared in a filter's finally
// scheduling: @SchedulerLock(name = "nightlyStock") (ShedLock) so one instance runs it
```
Layering enforced with ArchUnit: `layeredArchitecture().layer("Domain")...whereLayer("Domain").mayNotAccessAnyLayer()`.

## Manual trace checklist
1. Gateway routes -> Boot apps -> datasources: draw; note shared datasources.
2. Tenant/context propagation: `ThreadLocal` cleared? propagated to `@Async`/listeners?
3. Every outbound client: timeouts, retries, breaker, fallback behaviour.
4. Every listener: broker replicas, `acknowledge-mode`, idempotency key, DLQ (`x-dead-letter-exchange`, Kafka DLT).
5. Scheduled jobs: locking; what if the instance dies.
6. State: caches, sessions, WebSocket broker, local files vs replicas.
7. ADR/README claims vs the above.

## Stack-specific false positives
- `static final` constants and stateless utility classes.
- `@Cacheable` on reference data with TTL and `spring.cache.type=redis`.
- `new RestTemplate()` in tests or one-off CLI tooling.
- A `*-common` module with DTOs only and high fan-in.

## Tooling
- `mvn dependency:tree -pl <module>`, `gradle :module:dependencies` for the graph; `mvn com.github.ferstl:depgraph-maven-plugin:graph` for a picture.
- ArchUnit tests (`com.tngtech.archunit:archunit-junit5`), `jdeps` for package cycles, SonarQube architecture rules.
- `/actuator/health`, `/actuator/beans`, `/actuator/mappings` on a running instance (read-only) to confirm wiring.

## References
- Spring Boot reference (Production-ready features), Spring Cloud Gateway docs, Resilience4j docs, "Transactional outbox" (microservices.io), ArchUnit user guide.
- ASVS 1.x, CWE-306, CWE-362, CWE-770.
