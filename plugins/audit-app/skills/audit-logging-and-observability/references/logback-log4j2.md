# Logback and Log4j2 reference for audit-logging-and-observability

## Which one is in use

- Logback: default with `spring-boot-starter-logging`; config `logback-spring.xml`
  (preferred, supports `<springProfile>`) or `logback.xml`.
- Log4j2: `spring-boot-starter-log4j2` with `spring-boot-starter-logging` excluded;
  config `log4j2-spring.xml` / `log4j2.xml` / `.yaml` / `.properties`.
- Both behind SLF4J: `LoggerFactory.getLogger(X.class)` or Lombok `@Slf4j`.

## Log4Shell and version checks

`log4j-core` 2.0-beta9 to 2.14.1 is vulnerable to CVE-2021-44228 (JNDI lookup
RCE); the follow-ups CVE-2021-45046, CVE-2021-45105 and CVE-2021-44832 are fixed
in **2.17.1** (Java 8+), 2.12.4 (Java 7), 2.3.2 (Java 6). Flag any `log4j-core`
below 2.17.1 as Critical and hand it to `audit-dependency-vulnerabilities`.
`-Dlog4j2.formatMsgNoLookups=true` or `%m{nolookups}` is only a partial mitigation
on old versions. Log4j 1.x (`log4j:log4j`) is end-of-life (CVE-2019-17571,
CVE-2022-23305) - flag it too.

```bash
mvn dependency:tree -Dincludes=org.apache.logging.log4j:log4j-core,log4j:log4j
gradle dependencies --configuration runtimeClasspath | grep -E "log4j-core|log4j:log4j"
```

## Structured output

- Spring Boot 3.4+: `logging.structured.format.console=ecs|logstash|gelf` - JSON with no extra dependency.
- Logback: `net.logstash.logback.encoder.LogstashEncoder` in a `ConsoleAppender`;
  `<includeMdcKeyName>correlationId</includeMdcKeyName>`; `StructuredArguments.kv("orderId", id)`.
- Log4j2: `<JsonTemplateLayout eventTemplateUri="classpath:EcsLayout.json"/>`.
- A `PatternLayout` without `%X{traceId}` / `%X{correlationId}` means MDC values are set but never printed.

```xml
<springProfile name="prod">
  <appender name="JSON" class="ch.qos.logback.core.ConsoleAppender">
    <encoder class="net.logstash.logback.encoder.LogstashEncoder">
      <jsonGeneratorDecorator class="net.logstash.logback.mask.MaskingJsonGeneratorDecorator">
        <defaultMask>[REDACTED]</defaultMask>
        <path>password</path><path>token</path><path>authorization</path>
        <value>\b\d{13,16}\b</value>
      </jsonGeneratorDecorator>
    </encoder>
  </appender>
  <root level="INFO"><appender-ref ref="JSON"/></root>
</springProfile>
```

## Masking

- Logback pattern layouts: a custom `MaskingPatternLayout extends PatternLayout`
  overriding `doLayout` with regexes (for example `"password"\s*:\s*"[^"]*"`), or a
  `CompositeConverter` registered via `<conversionRule>`.
- logstash-logback-encoder: `MaskingJsonGeneratorDecorator` (field paths and value regexes, above).
- Log4j2: a `<Rewrite>` appender with a custom `RewritePolicy`, or
  `%replace{%m}{password=\S+}{password=***}` in the pattern.
- Masking is a safety net; the fix is still not passing the secret to the logger.

## MDC

- Put the id in a `OncePerRequestFilter` at `Ordered.HIGHEST_PRECEDENCE` and remove it
  in `finally` (pooled threads otherwise leak ids across requests).
- `@Async`, `CompletableFuture`, `ExecutorService`: MDC is thread-local; use a
  `TaskDecorator` / `ContextPropagatingTaskDecorator` (Boot 3.2+) or Micrometer context-propagation.
- Micrometer Tracing populates `traceId` and `spanId` in MDC automatically.

## Levels per profile

- `logging.level.root=INFO`; flag `DEBUG`/`TRACE` in `application-prod.yml` for
  `org.springframework.web`, `org.springframework.security`, `org.hibernate.SQL`,
  `org.hibernate.orm.jdbc.bind` (Hibernate 6) or
  `org.hibernate.type.descriptor.sql.BasicBinder` (Hibernate 5) - bind values include passwords and PII.
- `<springProfile name="!prod">` blocks are fine; check which profile production activates (`SPRING_PROFILES_ACTIVE`).

## Async appenders and loss

- Logback `AsyncAppender`: default `queueSize=256`; `discardingThreshold` drops
  TRACE/DEBUG/INFO when the queue is 80 percent full; `neverBlock=false`. Set
  `discardingThreshold=0` if Info events matter, and add `<shutdownHook/>` so the queue flushes.
- Log4j2 async loggers (LMAX Disruptor): `log4j2.asyncQueueFullPolicy=Discard` loses events silently.

## Rolling and retention

- Logback `SizeAndTimeBasedRollingPolicy`: `maxHistory` (periods kept), `totalSizeCap`,
  `maxFileSize`. No `maxHistory` means unbounded disk use; files inside a container
  are lost on restart anyway.
- Log4j2 `RollingFile` with
  `<DefaultRolloverStrategy max="30"><Delete basePath="logs"><IfLastModified age="30d"/></Delete></DefaultRolloverStrategy>`.
- Spring Boot properties: `logging.logback.rollingpolicy.max-history`, `logging.logback.rollingpolicy.total-size-cap`.

## Grep recipes

```bash
grep -rnE 'log\.(info|debug|warn|error|trace)\("[^"]*"\s*\+' src/main/java                 # concatenation
grep -rnE 'catch\s*\([^)]*\)\s*\{\s*log\.(debug|trace)\(' src/main/java                     # same-line low-level catch
grep -rnE 'printStackTrace\(\)|System\.(out|err)\.print' src/main/java
grep -rnE '%X\{|MDC\.put|LogstashEncoder|JsonTemplateLayout|structured\.format' src/main
grep -rnE 'hibernate\.(SQL|orm\.jdbc\.bind)|BasicBinder|org\.springframework\.web.*DEBUG' src/main/resources
grep -rnE 'maxHistory|totalSizeCap|DefaultRolloverStrategy' src/main/resources
```
