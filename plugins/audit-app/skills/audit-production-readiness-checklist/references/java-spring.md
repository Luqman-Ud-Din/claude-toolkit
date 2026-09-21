# Java / Spring Boot reference for audit-production-readiness-checklist

## Stack markers
`pom.xml`/`build.gradle` with `spring-boot-starter-*`; `application.yml|properties` (+ `application-{profile}.yml`); `bootstrap.yml` (Spring Cloud Config); Dockerfile with `SPRING_PROFILES_ACTIVE`.

## Where each checklist item lives
- **Env config:** profiles (`application-prod.yml`, `spring.profiles.active` set via env/JVM arg in Dockerfile/compose/k8s, never hard-coded in `application.yml`); `${ENV_VAR}` placeholders; Spring Cloud Config / Vault (`spring.cloud.vault`). Fail: single `application.yml` with production URLs, or `spring.profiles.active=prod` committed.
- **Secrets:** `spring.datasource.password`, `spring.rabbitmq.password`, `jwt.secret`, `*.api-key` with literal values in any `application*.yml|properties`; `application-prod.yml` with a real host + password = Critical.
- **Debug off:** `debug: true`, `spring.jpa.show-sql: true`, `logging.level.root: DEBUG` in prod profile; `spring.h2.console.enabled: true`; `management.endpoints.web.exposure.include: "*"` without security; `springdoc.swagger-ui.enabled` in prod without auth; `server.error.include-stacktrace: always`, `include-message: always`; `spring.devtools` on the classpath in the production artifact.
- **Health checks:** `spring-boot-starter-actuator` + `management.endpoint.health.probes.enabled: true` gives `/actuator/health/liveness` and `/readiness`; dependency checks come from auto-configured indicators (`DataSourceHealthIndicator`, `RabbitHealthIndicator`, `RedisHealthIndicator`, `MongoHealthIndicator`) - confirm they are not disabled (`management.health.db.enabled: false`) and that readiness includes them (`management.endpoint.health.group.readiness.include: db,rabbit`). Custom `HealthIndicator` beans for external APIs. Security config must `permitAll()` the health path. Probes in compose/k8s must target them.
- **Graceful shutdown:** `server.shutdown: graceful` + `spring.lifecycle.timeout-per-shutdown-phase: 30s` (default is immediate); `@PreDestroy` on listeners; Kafka/Rabbit listener containers stop on shutdown. Fail when `server.shutdown` absent and the app serves long requests.
- **Timeouts/retries:** `RestTemplate` via `RestTemplateBuilder.setConnectTimeout/setReadTimeout`, `WebClient` with `HttpClient.create().responseTimeout(...)`, Feign `feign.client.config.default.connectTimeout/readTimeout`, Resilience4j `@Retry/@CircuitBreaker/@TimeLimiter` with `resilience4j.*` config; JDBC `spring.datasource.hikari.connection-timeout`; `spring.rabbitmq.template.retry.enabled`.
- **Caching:** `spring.cache.type` (redis/caffeine/simple), `@EnableCaching`, `@Cacheable` with TTL config; `simple` (ConcurrentMap) behind >1 replica for authoritative data = fail.
- **Load test:** Gatling (`src/test/gatling`, `*.scala`/Java simulations), JMeter `*.jmx`, k6, `docs/perf*`.
- **Feature flags:** Togglz, FF4J, Unleash/LaunchDarkly SDKs, `@ConditionalOnProperty` feature toggles in `application-*.yml` (`features.*`).
- **Runbook / rollback / launch checklist:** docs; deploy pipeline (`helm rollback`, `kubectl rollout undo`, blue/green); Flyway/Liquibase reversibility (`audit-db-schema`).
- **Alerting:** Micrometer + Prometheus rules (`*.rules.yml`), Grafana alert provisioning, Datadog monitors in IaC; `management.metrics.export.*` shows the pipeline.

## What "good" looks like
```yaml
# application-prod.yml
spring:
  datasource:
    url: ${DB_URL}
    username: ${DB_USER}
    password: ${DB_PASSWORD}
  jpa: { show-sql: false, hibernate: { ddl-auto: validate } }
server:
  shutdown: graceful
  error: { include-stacktrace: never, include-message: never }
management:
  endpoints.web.exposure.include: health,info,prometheus
  endpoint.health: { probes.enabled: true, show-details: when-authorized, group.readiness.include: db,rabbit,redis }
resilience4j.timelimiter.instances.fbr.timeoutDuration: 10s
```

## Manual trace checklist
1. Dockerfile/compose/k8s: which profile is active; which `application-*.yml` wins; literals in it.
2. Actuator: health path permitted in `SecurityFilterChain`; readiness group includes DB/broker; probes configured.
3. Every outbound client: timeouts + Resilience4j config present.
4. `server.shutdown` and listener container shutdown.
5. Pipeline rollback step; last migration reversible.

## Stack-specific false positives
- `application-dev.yml`/`application-local.yml` with `localhost` and dev passwords.
- `management.endpoints.web.exposure.include: "*"` when the management port is internal-only (`management.server.port` + network policy) - Low, note it.
- `ddl-auto: validate` is fine; `update` is the finding.

## Tooling
- `./mvnw spring-boot:run -Dspring-boot.run.profiles=prod` against a scratch env to see effective config; `curl localhost:8080/actuator/health/readiness`.
- `./mvnw dependency:list | grep -i "actuator\|resilience4j\|togglz"`.

## References
- Spring Boot docs: Production-ready features (health, Kubernetes probes), Graceful shutdown, Externalized configuration, Profiles.
- CWE-798, CWE-489, CWE-215, ASVS 14.x, OWASP A05:2021.
