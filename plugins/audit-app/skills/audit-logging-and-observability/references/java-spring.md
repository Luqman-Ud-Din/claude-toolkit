# Java / Spring reference for audit-logging-and-observability

## Stack markers

`pom.xml` / `build.gradle` with `spring-boot-starter-*`. Logging is SLF4J over
Logback by default (`spring-boot-starter-logging`); Log4j2 if
`spring-boot-starter-log4j2` replaces it. Observability: `spring-boot-starter-actuator`,
`micrometer-registry-*`, `micrometer-tracing-bridge-otel` (Boot 3) or Spring
Cloud Sleuth (Boot 2, end-of-life), or the OpenTelemetry Java agent (`-javaagent:opentelemetry-javaagent.jar`
in the Dockerfile).

## Where the relevant code lives

- `src/main/resources/logback-spring.xml` / `logback.xml` / `log4j2-spring.xml` -
  appenders, encoder (JSON or pattern), levels, MDC keys in the pattern.
- `application*.yml|properties` - `logging.level.*`, `logging.structured.format.console`
  (Boot 3.4+), `management.tracing.sampling.probability`,
  `management.otlp.*`, `management.endpoints.web.exposure.include`.
- `config/`, `filter/`, `interceptor/` - `OncePerRequestFilter`s, `HandlerInterceptor`s,
  `@ControllerAdvice` exception handlers.
- `security/` - `AuthenticationEventPublisher`, `AuthenticationFailureHandler`,
  `AccessDeniedHandler`.

## Dangerous / interesting APIs and patterns

- `log.info("login " + request)` / `String.format` - concatenation, no structure,
  `toString()` of a DTO (Lombok `@Data` prints every field including `password`).
- `log.debug("payload {}", objectMapper.writeValueAsString(body))`,
  `CommonsRequestLoggingFilter` with `setIncludePayload(true)` / `setIncludeHeaders(true)`.
- `logging.level.org.springframework.web=DEBUG` or
  `logging.level.org.hibernate.orm.jdbc.bind=TRACE` in a production profile - bind
  parameter values (passwords, PII) in the log.
- `catch (Exception e) { log.debug("...", e); }`, `log.warn(e.getMessage())`,
  `e.printStackTrace()`, `System.out.println`.
- `@ControllerAdvice` that returns 500 without logging, or logs at `info`.
- Missing `MDC.put("correlationId", ...)` / no `%X{traceId}` in the pattern.
- `RestTemplate` built with `new RestTemplate()` (no `RestTemplateBuilder`) and
  `WebClient.create()` - bypass Micrometer observation, so no trace propagation.
- `@Async` / `ExecutorService` without `ContextPropagatingTaskDecorator` - MDC is
  thread-local and is lost in the worker thread.

## What "good" looks like

```yaml
# application-prod.yml (Boot 3.4+)
logging:
  structured.format.console: ecs          # JSON to stdout
  level: { root: INFO, com.acme: INFO }
management:
  tracing.sampling.probability: 0.1
  otlp.tracing.endpoint: http://otel-collector:4318/v1/traces
  endpoints.web.exposure.include: health,prometheus
```

```java
@Component @Order(Ordered.HIGHEST_PRECEDENCE)
class CorrelationIdFilter extends OncePerRequestFilter {
  protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain) throws IOException, ServletException {
    String cid = Optional.ofNullable(req.getHeader("X-Correlation-Id")).orElse(UUID.randomUUID().toString());
    MDC.put("correlationId", cid); res.setHeader("X-Correlation-Id", cid);
    try { chain.doFilter(req, res); } finally { MDC.remove("correlationId"); }
  }
}

@EventListener void onFailure(AbstractAuthenticationFailureEvent e) {
  log.warn("auth.failure user={} reason={}", e.getAuthentication().getName(), e.getException().getClass().getSimpleName());
}
```

Logback JSON without Boot 3.4: `net.logstash.logback.encoder.LogstashEncoder`
with `<includeMdcKeyName>correlationId</includeMdcKeyName>`. Mark sensitive DTO
fields with `@ToString.Exclude` and `@JsonIgnore` on the logged projection.

## Manual trace checklist

1. The filter chain: is a correlation/trace id put in MDC before Spring Security,
   and does the encoder/pattern output it?
2. Authentication events: `AuthenticationSuccessEvent`, failure events,
   `AuthorizationDeniedEvent` (Spring Security 6) - listened to and logged?
3. `@ControllerAdvice`: the 500 handler logs the exception at `error` exactly once.
4. Every `toString()`-able DTO that reaches a log call: Lombok `@Data` on a class
   with `password`, `token`, `iban`, `cardNumber`.
5. Outbound clients built from `RestTemplateBuilder` / `WebClient.Builder` beans so
   `traceparent` propagates; Kafka/RabbitMQ observation enabled.
6. Production profile levels: no DEBUG/TRACE on web, security or SQL bind loggers.

## Stack-specific false positives

- `log.debug(..., e)` in a retry loop that logs `error` after the final attempt.
- `System.out.println` in `src/test/**` or a `CommandLineRunner` used only locally.
- `CommonsRequestLoggingFilter` registered only under `@Profile("dev")`.
- `password` in a log message that is a constant like `"password reset email sent"`.

## Tooling

```bash
mvn dependency:tree | grep -Ei "logback|log4j|micrometer|opentelemetry|sleuth"
grep -rnE "log\.(info|debug|warn|error|trace)\(" src/main/java
grep -rnE "printStackTrace|System\.out\.print" src/main/java
```
SpotBugs / `find-sec-bugs` rule `CRLF_INJECTION_LOGS` (CWE-117); Error Prone
`Slf4jFormatShouldBeConst`; PMD `GuardLogStatement`, `AvoidPrintStackTrace`.

## References

- Spring Boot reference: Logging, Structured Logging, Observability, Tracing.
- Logback / logstash-logback-encoder; Micrometer Tracing; OTel Java agent.
- CWE-532, CWE-117, CWE-778; ASVS 7.1-7.3; OWASP A09:2021.
