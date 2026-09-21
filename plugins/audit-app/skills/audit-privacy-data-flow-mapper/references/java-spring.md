# Java / Spring reference for audit-privacy-data-flow-mapper

## Stack markers
`pom.xml` / `build.gradle` with `spring-boot-starter-*`. Variants: JPA/Hibernate
entities vs JDBC/MyBatis SQL, Logback/Log4j2 via SLF4J, Spring Cache
(`@Cacheable`) over Redis/Caffeine, Spring Batch/`@Scheduled` jobs, Thymeleaf/
FreeMarker templates, Feign/RestTemplate/WebClient for outbound calls.

## Where the relevant code lives
- Storage: `@Entity` classes (`domain/`, `model/`, `entity/`), `@Column(name=...)`,
  Flyway/Liquibase migrations (`db/migration/*.sql`, `changelog*.xml/yaml`),
  `@Document` (MongoDB), `RedisTemplate` usage, file uploads (`MultipartFile` -> disk/S3).
- Collection: `@RestController` methods with `@RequestBody` DTOs, `@RequestParam`,
  `@PathVariable`, `@ModelAttribute` forms, WebSocket `@MessageMapping`, Kafka/RabbitMQ listeners.
- Processors: `log.info(...)` (Lombok `@Slf4j`), MDC, `@Cacheable(key=...)`,
  Micrometer tags, Sentry/Bugsnag, Spring Batch writers, JasperReports/Excel exports.
- Transmission: `RestTemplate`, `WebClient`, `@FeignClient(url=...)`, `JavaMailSender`,
  Twilio/SendGrid SDKs, Kafka producers to other systems, SFTP uploads.
- Templates: `src/main/resources/templates/**` (Thymeleaf `th:text="${user.email}"`),
  FreeMarker `${email}`, `messages.properties` with placeholders.

## Dangerous / interesting APIs and patterns
- `log.info("Registered {}", user)` with Lombok `@Data`/`@ToString` - every field printed.
- `log.info("Login for {}", request.getEmail())`.
- `MDC.put("user", email)` - on every subsequent line in the request.
- `@Cacheable(value="users", key="#email")`; `redisTemplate.opsForValue().set("user:" + email, ...)`.
- `@GetMapping("/users/{email}")`, `@RequestParam String email` on GET.
- `Sentry.setUser(new User(){{ setEmail(...) }})`; `SentryOptions.setSendDefaultPii(true)`.
- `restTemplate.postForObject("https://api.vendor.com/...", userDto, ...)` - whole DTO sent.
- Jackson: no `@JsonIgnore` on entity PII returned directly from a controller.
- `spring.jpa.show-sql=true` / Hibernate `org.hibernate.type=TRACE` - bound parameters (PII) in logs.
- Actuator `/actuator/httptrace` or `/env` exposing request data.
- JPA `@Convert(converter = AttributeEncryptor.class)` absent on PII columns (at-rest encryption).

## What "good" looks like
```java
log.info("Customer {} registered", customer.getId());
@Cacheable(value = "customers", key = "T(org.apache.commons.codec.digest.DigestUtils).sha256Hex(#email)")
@JsonIgnore private String nationalId;
// application.yml
logging.level.org.hibernate.type: INFO   # never TRACE in prod
```

## Manual trace checklist
1. Logback/Log4j2 appenders (`logback-spring.xml`): where do logs go (file,
   Logstash, CloudWatch, Datadog)? Retention settings there.
2. `show-sql` / `hibernate.type` TRACE / `p6spy` in any profile -> bound PII in logs.
3. Every `@FeignClient` / `RestTemplate` base URL -> vendor; the request DTO's fields.
4. `JavaMailSender` host and template variables; SMS SDK usage.
5. Exports (`@Scheduled` jobs writing CSV/XLSX, SFTP pushes) - storage and transfer.
6. Kafka/RabbitMQ topics carrying PII - consumers are processors; the broker is storage (retention.ms).
7. Actuator endpoints exposed in prod.

## Stack-specific false positives
- `log.debug` guarded by `isDebugEnabled()` and disabled in prod - still report as Low; config can change.
- `@Column(name="email")` on a `Company` entity - business contact.
- `${email}` in `messages.properties` used for the *sender* address.
- Test fixtures under `src/test` with `example.com` addresses.

## Tooling
- `python scripts/pii_scan.py <repo> ...`; `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/java-spring.json`
- `grep -rn "show-sql\|hibernate.type\|p6spy" src/main/resources`
- `mvn dependency:list | grep -i "twilio\|sendgrid\|sentry\|mixpanel\|segment"` to list vendor SDKs
- Flyway/Liquibase changelogs as the schema source: `grep -rni "email\|phone" src/main/resources/db`

## References
GDPR Art.5(1)(c), 5(1)(e), 28, 30, 32; CWE-532, CWE-359, CWE-598; ASVS 8.3, 7.1.1;
Spring Boot logging docs (`logging.*`), Spring Cache SpEL keys, Sentry Java
`sendDefaultPii` docs.
