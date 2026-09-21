# Java / Spring reference for audit-datetime-and-timezone

## Stack markers
`pom.xml` / `build.gradle` with `spring-boot-starter-*`. Variants: JPA/Hibernate (5 vs 6: different default `Instant`/`OffsetDateTime` mapping), Jackson, `@Scheduled` vs Quartz, Flyway/Liquibase migrations, legacy `java.util.Date`/`Calendar` still present.

## Where the relevant code lives
- Entities: `@Entity` classes (`LocalDateTime` vs `Instant`/`OffsetDateTime`/`ZonedDateTime`), `@Column(columnDefinition=...)`, `application.yml` (`spring.jpa.properties.hibernate.jdbc.time_zone`, `spring.jackson.time-zone`), migrations (`V*__*.sql`, `changelog*.xml`).
- Business: `*Service.java` using `LocalDate.now()`, `LocalDateTime.now()`, `ChronoUnit`, `Period`.
- Edges: DTOs, `@JsonFormat(pattern=...)`, `@DateTimeFormat`, `ObjectMapper` config, `Converter<String, LocalDate>`.
- Jobs: `@Scheduled(cron=...)`, Quartz `CronTrigger`, `TaskScheduler`.
- Tests: `Clock` beans, `Clock.fixed`, `Mockito.mockStatic(Instant.class)`, `Thread.sleep`.

## Dangerous / interesting APIs and patterns
- `LocalDateTime.now()`, `LocalDate.now()`, `new Date()`, `Calendar.getInstance()`, `System.currentTimeMillis()` for stored instants or cutoffs (all JVM-zone dependent except millis, which then get converted with the default zone).
- `LocalDateTime` fields for instants (no zone; Hibernate writes them as JVM-local unless `hibernate.jdbc.time_zone=UTC`); `java.util.Date` on entities; `@Temporal(TemporalType.DATE)` used for instants.
- `ZoneId.systemDefault()`, `TimeZone.getDefault()`, `ZonedDateTime.now()` without a zone argument in server code.
- `SimpleDateFormat` (not thread-safe, default zone), `DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")` for API output (no offset), `@JsonFormat(pattern = "dd/MM/yyyy")` on instants, `spring.jackson.time-zone` unset with `WRITE_DATES_AS_TIMESTAMPS=false`.
- `LocalDateTime.parse(str)` / `LocalDate.parse(str)` of client input treated as UTC; `Instant.parse` on strings without `Z` (throws) worked around by appending `Z`.
- `plusDays(1)` as 24 h, `plusMonths(1)` from the 31st, `Duration.between(localA, localB)` across DST; `LocalDate.atStartOfDay()` without a zone compared to `Instant`.
- `@Scheduled(cron = "0 0 2 * * *")` with no `zone`; Quartz trigger without `inTimeZone`.
- SQL: `CURRENT_TIMESTAMP`/`NOW()` defaults in migrations, `DATE(created_at)` grouping, `timestamp` (not `timestamptz`) columns in Postgres.
- Sorting on formatted strings; `compareTo` between `LocalDateTime` from different zones.
- Tests calling `Instant.now()` directly instead of a `Clock` bean; assertions like `assertEquals(LocalDate.now(), dto.date)`.

## What "good" looks like
```java
@Entity class Order { @Column(columnDefinition = "timestamptz") private Instant createdAt; private LocalDate invoiceDate; }
@Configuration class ClockConfig { @Bean Clock clock() { return Clock.systemUTC(); } }
@Service class TrialService { private final Clock clock; boolean expired(Sub s) { return !s.getTrialEndsAt().isAfter(Instant.now(clock)); } }
// day window in the branch zone
ZoneId zone = ZoneId.of(branch.getIanaZone());
Instant start = day.atStartOfDay(zone).toInstant(); Instant end = day.plusDays(1).atStartOfDay(zone).toInstant();
@Scheduled(cron = "0 0 2 * * *", zone = "Asia/Karachi")
```
`application.yml`: `spring.jpa.properties.hibernate.jdbc.time_zone: UTC`, `spring.jackson.time-zone: UTC`, `spring.jackson.serialization.write-dates-as-timestamps: false`; JVM `-Duser.timezone=UTC`. Tests: `Clock.fixed(Instant.parse("2024-03-10T01:30:00Z"), ZoneOffset.UTC)`.

## Manual trace checklist
1. Date-field map: every temporal field type on entities and DTOs, column type in migrations, `hibernate.jdbc.time_zone` value.
2. Every `now()` without a `Clock`: what decision it feeds and in which zone the user expects it.
3. Jackson config and `@JsonFormat` patterns: does every instant leave with an offset.
4. `@Scheduled`/Quartz: `zone` present; job body uses `Instant`.
5. Reports: JPQL/SQL grouping by day on UTC columns without zone conversion.
6. Tests: `Clock` injection present; DST/month-end cases.

## Stack-specific false positives
- `LocalDate` for true date-only concepts (birth date, invoice date) is correct.
- `LocalDateTime` combined with an explicit `ZoneId` in the same expression (`.atZone(zone).toInstant()`) is a conversion at the edge; confirm the zone is stored, not `systemDefault()`.
- `Instant.now()` in a log statement or metric.
- `@Scheduled(fixedRate = ...)` needs no zone (elapsed interval).

## Tooling
`grep -rn "LocalDateTime.now\|LocalDate.now\|new Date()\|systemDefault\|SimpleDateFormat" --include=*.java`; `grep -rn "time_zone\|time-zone\|user.timezone" src/main/resources`; Error Prone `JavaTimeDefaultTimeZone` and `JdkObsolete` checks; `mvn -Duser.timezone=Asia/Karachi test` to expose zone-dependent tests.

## References
JSR-310 (`java.time`) javadoc; Hibernate `hibernate.jdbc.time_zone`; Spring `@Scheduled` zone attribute; Jackson `JavaTimeModule`; ISO 8601; CWE-682, CWE-704.
