# Java / Spring (JPA, Hibernate, Flyway, Liquibase) reference for audit-db-schema

## Stack markers
`pom.xml`/`build.gradle` with `spring-boot-starter-data-jpa`, `flyway-core`, `liquibase-core`, `spring-data-jdbc`, `jooq`, `mybatis`. Variants: Flyway-managed SQL migrations (most common), Liquibase changelogs (XML/YAML/formatted SQL), `spring.jpa.hibernate.ddl-auto=update` (schema generated from entities - a finding by itself in production).

## Where the relevant code lives
- `src/main/java/**/domain|entity|model/*.java` - `@Entity` classes.
- `src/main/resources/db/migration/V<version>__<desc>.sql` (Flyway), `db/migration/U<version>__<desc>.sql` (undo, Teams edition or manual), `R__*.sql` repeatable.
- `src/main/resources/db/changelog/db.changelog-master.{xml,yaml}` and included files (Liquibase).
- `application.yml`: `spring.jpa.hibernate.ddl-auto`, `spring.jpa.properties.hibernate.jdbc.time_zone`, `spring.flyway.*`, `spring.liquibase.*`.
- Seed: `data.sql`, `import.sql`, Flyway `V*__seed*.sql`, Liquibase `loadData`.

## Dangerous / interesting APIs and patterns
- `private double|float price|amount|total|balance` - money in binary float; must be `BigDecimal` with `@Column(precision = 18, scale = 4)`.
- `BigDecimal` without `precision/scale` - Hibernate defaults to `numeric(19,2)`.
- `LocalDateTime` for instants (no zone) - use `Instant`/`OffsetDateTime` mapped to `timestamptz`/`datetimeoffset`; `hibernate.jdbc.time_zone=UTC` as a fallback.
- `String` fields without `@Column(length = n)` -> `varchar(255)` default (silently truncates or fails), `@Lob`/`columnDefinition = "TEXT"` for codes and names.
- `@ManyToOne` without `@JoinColumn` naming or without an index: Hibernate does **not** create indexes for FKs on Postgres/SQL Server (MySQL InnoDB does). Look for `@Table(indexes = {@Index(columnList = "customer_id")})` or a `CREATE INDEX` in a migration.
- `@OneToMany(cascade = CascadeType.ALL, orphanRemoval = true)` on references to shared entities; `CascadeType.REMOVE` on many-to-many.
- `@Id` missing (compile error) vs `@IdClass`/`@EmbeddedId` with nullable parts; `@GeneratedValue(strategy = AUTO)` on MySQL -> table generator contention.
- No `@Version` on editable aggregates - no optimistic locking.
- Soft delete via `@SQLDelete`/`@Where(clause = "deleted = false")` (Hibernate 6: `@SoftDelete`) without an index on `deleted` and without partial unique indexes.
- `ddl-auto: update|create|create-drop` in any non-test profile.
- Flyway `V` script with `DROP COLUMN|DROP TABLE|ALTER COLUMN ... TYPE` and no `U` script; `spring.flyway.clean-disabled=false`.
- Liquibase `changeSet` with `<sql>`, `<dropColumn>`, `<update>`, `<delete>` and no `<rollback>` (createTable/addColumn/createIndex auto-generate rollback; the rest do not).
- `data.sql` inserting users with real-looking emails or bcrypt hashes copied from production.
- `password`, `ssn`, `cardNumber`, `iban` fields as plain `String` with no `AttributeConverter` encryption or hashing.

## What "good" looks like
```java
@Entity
@Table(name = "order_lines",
       indexes = { @Index(name = "ix_order_lines_order", columnList = "order_id"),
                   @Index(name = "ix_order_lines_product", columnList = "product_id") })
public class OrderLine {
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY) private Long id;
    @ManyToOne(fetch = FetchType.LAZY, optional = false) @JoinColumn(name = "order_id") private Order order;
    @Column(precision = 18, scale = 4, nullable = false) private BigDecimal unitPrice;
    @Column(length = 64, nullable = false) private String sku;
    @Column(nullable = false) private Instant createdAt;
    @Version private long version;
}
```
Flyway: `V12__add_order_lines.sql` paired with `U12__add_order_lines.sql` (or a documented forward-fix policy); Liquibase: every `changeSet` with an explicit `<rollback>` for non-auto-reversible changes.

## Manual trace checklist
1. List every `@Entity`; cross-check with the latest Flyway/Liquibase state (tables created across all `V*` scripts). Entities without a migration, or migrations without an entity, are drift.
2. Money aggregates: `BigDecimal` + explicit scale in entity **and** `numeric(p,s)` in the migration.
3. Hot repository queries (`@Query`, derived `findByCustomerIdAndStatusOrderByCreatedAtDesc`) - map each to an index.
4. Cascade: trace `deleteById` on a root; check `@OnDelete(action = CASCADE)` (DB-level) vs `CascadeType.REMOVE` (ORM-level, N+1 deletes).
5. `ddl-auto` per profile; production must be `validate` or `none`.
6. Confirm `spring.jpa.open-in-view=false` is out of scope here (ORM audit) but note it.

## Stack-specific false positives
- `LocalDate` for calendar dates (birthdays, due dates) is correct.
- Missing `U` scripts are the norm in Flyway Community; downgrade to Medium if the team documents a "forward-fix only" policy and has tested restores.
- `@Index` absence on MySQL InnoDB FKs: the engine adds one automatically.
- `double` on physical measures (weight, length) not summed into money.

## Tooling
- `./mvnw flyway:info` / `./gradlew flywayInfo` - applied vs pending.
- `liquibase status --verbose`, `liquibase rollback-sql <tag>` to see whether rollback is generable.
- `spring.jpa.hibernate.ddl-auto=validate` on a scratch DB to detect entity/schema drift.
- Postgres: `SELECT * FROM pg_stat_user_indexes WHERE idx_scan = 0` (unused), missing FK indexes query from the Postgres wiki.
- `jOOQ` / `SchemaCrawler` (`schemacrawler --command=schema --info-level=maximum`) to dump a live schema read-only.

## References
- Hibernate ORM user guide (Identifiers, Optimistic locking, Soft delete), Spring Data JPA reference.
- Flyway "Undo migrations", Liquibase "Rollback" docs.
- CWE-682, CWE-311, CWE-916, CWE-20; ASVS 2.4, 6.2, 8.3.
