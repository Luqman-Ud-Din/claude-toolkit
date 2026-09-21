---
name: audit-db-schema
description: Reviews a relational database schema from migrations, DDL scripts, ORM models, or a live connection for missing primary keys, foreign keys and cascade rules, missing or redundant indexes, wrong data types (float money, naive timestamps, unbounded strings), nullability, unique and check constraints, naming, audit columns, soft delete, sensitive-column encryption, concurrency tokens, and migration hygiene (reversible, no data loss, model in sync, no PII in seed data). Use it whenever the user asks about database schema, tables, columns, indexes, migrations, data types, constraints, EF Core or JPA or Prisma or Django models, slow queries that smell like a missing index, "is the DB designed right", or as the data part of a readiness or performance audit - even when they do not say "schema" or name this skill.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-app:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: database schema

Reviews the schema the application actually ships - not the one people think it
has - and reports table-by-table whether it will hold up in production: keys,
indexes, types, constraints, audit and soft-delete conventions, sensitive
columns, and whether migrations can be rolled back without losing data.

Read-only rule: never modify the audited code, migrations, or database. Write
only under `audit/`. A live connection, if used, is read-only (`SELECT` on
catalog views) and must be offered, never required.

## Inputs and prerequisites

- Repository root (both halves if backend and frontend live apart).
- Schema sources, in order of trust:
  1. Migrations (`Migrations/*.cs` + `*ModelSnapshot.cs`, `db/migration/V*.sql`,
     `migrations/000*.py`, `prisma/migrations/*/migration.sql`, `knex` files).
  2. DDL scripts (`*.sql` with `CREATE TABLE`, `ALTER TABLE`, `CREATE INDEX`).
  3. ORM models (EF entities and fluent config, JPA `@Entity`, TypeORM/Prisma,
     Django `models.py`).
  4. Live connection (optional): if the user offers a read-only connection
     string, dump `INFORMATION_SCHEMA.TABLES/COLUMNS/KEY_COLUMN_USAGE` and
     `sys.indexes` (SQL Server), `pg_indexes` (Postgres) or `SHOW CREATE TABLE`
     (MySQL) into `audit/evidence/audit-db-schema/live-schema.sql` and treat it
     as source 1. Do not ask for credentials; work from the repo when none are given.
- `audit/stack.json` if `audit-application` already ran; otherwise run
  `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>` (without `--write`).
- Python 3 (stdlib only) for the bundled scripts.
- Skills from the `audit-core` plugin (reached via `$AUDIT_CORE_ROOT`, exported by that plugin; a sibling `skills/` layout also works): `audit-stack-detection`,
  `audit-code-scan` (grep pass and the shared file walker), `audit-sensitive-data-catalog`
  (sensitive column names and seed-data PII values) and `audit-finding-writer` (findings I/O).

## Workflow

1. **Resolve the stack.** `python "$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py" <repo>` (honours
   `audit/stack.json`). Open only `references/<stack>.md` for the detected
   backend; open the matching frontend file only for the "what the client sends"
   checks. Unknown stack: use `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md` and say so in
   `scope.not_checked`.
2. **Automated pass.**
   - `python scripts/schema_checklist.py <repo> --stack <id> --out audit/evidence/audit-db-schema/checklist.json --md audit/evidence/audit-db-schema/checklist.md`
     parses DDL and ORM models into a table-by-table checklist (pk, fks, indexes,
     money types, timestamp types, string bounds, audit columns, soft delete,
     concurrency token, sensitive plaintext columns named by `audit-sensitive-data-catalog` -
     hashed, encrypted and masked names are skipped) and proposes indexes with the queries
     that justify them.
   - `python scripts/migration_reversibility.py <repo> --out audit/evidence/audit-db-schema/migrations.json --md audit/evidence/audit-db-schema/migrations.md`
     grades every migration: reversible / irreversible / data-loss / raw SQL /
     seed PII (emails, phones, IBANs, Luhn-valid cards and password hashes found by
     `audit-sensitive-data-catalog`; placeholders and role mailboxes skipped).
   - `python "$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py" <repo> --patterns scripts/patterns/<stack>.json --out audit/evidence/audit-db-schema/hits.json`
     for the code-side smells (float money properties, naive `DateTime`,
     hard deletes, cascade on shared references, raw SQL in migrations).
   Every hit is a candidate. Confirm it in the file before it becomes a finding.
3. **Manual trace of the highest-risk tables** (see the stack file's checklist):
   money tables (orders, invoices, payments, ledgers), identity tables (users,
   tokens), the biggest tables (sale/purchase detail rows, logs, events), and
   any table two services write. For each: who reads it and with which filters,
   does an index cover those filters, do the cascade rules match what the
   business expects on delete, is soft delete applied consistently in queries,
   and is the "model in sync with migrations" claim true (EF: last snapshot vs
   entities; Django: `makemigrations --check`; Prisma: `migrate diff`).
4. **Write findings** with `python "$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py"` (`init`, then `add` one JSON
   per finding, then `md`). Use the `DB-` prefix. One root cause per finding: a
   missing index on every FK is one finding with many locations, not twenty.
5. **Produce the outputs** at the fixed paths:
   - `audit/findings/audit-db-schema.json`
   - `audit/reports/audit-db-schema.md` (template below)
   - `audit/evidence/audit-db-schema/` (checklist, migration report, hits, live dump)
   - `audit/status/audit-db-schema.json`:
     the status record defined in `audit-core:audit-finding-writer` (references/run-status.md)
6. **List what was not checked** and why: tables only defined in a live DB you
   could not reach, stored procedures, index usage statistics (need a live DB),
   encryption at rest (belongs to `audit-infra-and-deployment`), query plans
   (`audit-performance-and-scalability`), tenant filters (`audit-multi-tenant-isolation`),
   and schema files inside folders the shared walker skips (`repo_walk.SKIP_DIRS` in `audit-code-scan`).

## What to check, per table

| Check | Bad | Good |
|---|---|---|
| Primary key | heap table, composite natural key with nullable parts | surrogate or stable natural PK, clustered where the engine cares |
| Foreign keys | none, or `ON DELETE CASCADE` from a shared reference (company, product) | FK present; cascade only from parent to owned children (order -> order lines) |
| Indexes | FK columns unindexed, filtered/sorted columns unindexed, duplicate/prefix-redundant indexes | index per FK, composite index matching the hottest `WHERE ... ORDER BY` |
| Money | `float`/`real`/`double` | `decimal(18,4)` / `numeric`, currency column beside it |
| Timestamps | `datetime` local, `timestamp without time zone`, `DateTime` in C# | `datetimeoffset`/`timestamptz`/UTC-by-convention documented |
| Strings | `nvarchar(max)`/`TEXT` for names and codes | bounded `nvarchar(n)` matching the UI validator |
| Nullability | everything nullable, or `NOT NULL` with a magic default | mirrors the business rule; unique on natural keys |
| Constraints | none | `UNIQUE` on codes/emails per tenant, `CHECK (qty >= 0)` |
| Naming | mixed `CustomerID`/`customer_id`/`CustId` | one convention, FK named after the referenced table |
| Audit columns | absent or inconsistent | `CreatedAt/By`, `UpdatedAt/By` on every business table |
| Soft delete | `IsDeleted` column with no filter or index and no unique-constraint handling | global query filter, filtered unique index `WHERE IsDeleted = 0` |
| Sensitive columns | plaintext passwords, card numbers, national ids | hash (Argon2/bcrypt/PBKDF2), column-level encryption or tokenisation, documented |
| Concurrency | none on editable rows | `rowversion`/`@Version`/`xmin` |
| Migrations | empty `Down()`, no `U__` script, `RunPython` without reverse, `DropColumn` without backup | reversible, additive first, data migration separate from schema change |

## Finding format

Write findings using `audit-core:audit-finding-writer`, with ID prefix `DB`.
Use its canonical schema and severity rubric. Topic-specific field guidance:

- **Location:** `path/to/file.ext:LINE` (table or symbol)
- **Evidence:**

```lang
<the exact DDL / model lines, or the script output>
```

- **Impact:** Plain language: what breaks, who notices, when (at what row count or on which flow).
- **Remediation:** The concrete change in this stack (migration snippet or model attribute), and the safe rollout order.
- **Reference:** CWE-nnn, ASVS-x.y.z where a security angle exists; otherwise the engine doc and `tags: ["quality"]`


Severity guide for this skill (rubric: `$AUDIT_CORE_ROOT/skills/audit-finding-writer/references/severity-rubric.md`):
Critical = data loss or corruption at production load (irreversible migration
that drops data, float money in a ledger, plaintext secrets); High = visible
degradation or wrong results (unindexed FK on the main list, cascade that
deletes shared rows, naive timestamps driving cut-offs); Medium = measurable
cost (missing audit columns, unbounded strings, redundant index); Low/Info =
naming and hygiene.

## Output template (`audit/reports/audit-db-schema.md`)

```markdown
## audit-db-schema

**Sources used:** migrations (n files) | DDL (n files) | ORM models (n classes) | live DB (yes/no)
**Tables reviewed:** n  **Findings:** Critical n / High n / Medium n / Low n / Info n

### Table-by-table checklist
| Table | PK | FKs (indexed/total) | Money type | Timestamps | String bounds | Audit cols | Soft delete | Concurrency | Issues |
|---|---|---|---|---|---|---|---|---|---|
| Orders | yes | 2/3 | decimal | datetimeoffset | ok | yes | IsDeleted | rowversion | FK CustomerId unindexed |

### Findings
(standard blocks, highest severity first)

### Recommended indexes
| Table | Columns | Type | Justifying query / code path | Expected effect |
|---|---|---|---|---|
| Orders | (CustomerId, CreatedAt DESC) | non-clustered | `OrderController.GetPaginationList` -> `Where(o => o.CustomerId == id).OrderByDescending(o => o.CreatedAt)` | removes scan on the main list |

### Migration reversibility report
| Migration | Tool | Reversible | Data loss | Raw SQL | Seed PII | Note |
|---|---|---|---|---|---|---|
| 20260901_AddDiscount | EF Core | no (empty Down) | no | no | no | add DropColumn("Discount") to Down |

### Not checked
- item - reason
```

## Examples

**Input (DDL):** `db/schema.sql:41: Price FLOAT NOT NULL` in `CREATE TABLE OrderLines`

**Output:**
```markdown
### [Critical] DB-002 - Order line price stored as FLOAT
- **Location:** `db/schema.sql:41` (OrderLines.Price)
- **Confidence:** confirmed
- **Evidence:**

```sql
Price FLOAT NOT NULL,   -- summed into Orders.Total by InvoiceManager.Recalculate
```

- **Impact:** Binary floating point cannot represent 0.10 exactly; invoice totals drift by cents as lines accumulate and will not reconcile with the tax authority submission. Rated Critical because it moves money and the error is silent.
- **Remediation:** Add a migration that creates `Price DECIMAL(18,4)`, copies the values with `ROUND(Price, 4)`, drops the old column, and updates the entity to `[Column(TypeName = "decimal(18,4)")] public decimal Price`. Reconcile historical totals once after the change.
- **Reference:** CWE-682; tags: money, data-integrity
```

**Input (script output):** `migration_reversibility.py` -> `Migrations/20260810_AddCustomerNotes.cs: Down() empty`

**Output:** `[High] DB-005 - Migration AddCustomerNotes cannot be rolled back` with
remediation "mirror each `AddColumn` in `Up()` with `DropColumn` in `Down()`;
verify with `dotnet ef migrations script <prev> <this>` and the reverse order".

## Bundled files

- `references/<stack>.md` - where the schema lives, what to grep, what good looks like, false positives, tooling, per stack (`dotnet`, `java-spring`, `node-express`, `python-django`, `angular`, `react`, `vue`); to add a stack, copy `$AUDIT_CORE_ROOT/skills/audit-stack-detection/references/stack-reference-template.md`.
- `references/schema-checklist.md` - the full per-table checklist with engine-specific type advice (SQL Server, Postgres, MySQL, SQLite) and index design rules.
- `references/migration-hygiene.md` - reversibility rules per migration tool and the safe expand/contract pattern.
- `scripts/schema_checklist.py` - DDL + ORM parser producing the table checklist and recommended indexes; sensitive column names come from `audit-sensitive-data-catalog` (hashed passwords are not flagged).
- `scripts/migration_reversibility.py` - EF Core / Flyway / Liquibase / Django / Alembic / Knex / Prisma reversibility and data-loss checker; seed-data PII values come from `audit-sensitive-data-catalog`.
- `scripts/patterns/<stack>.json` - code-side smell patterns, run with `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`.
- Atomic scripts called: `$AUDIT_CORE_ROOT/skills/audit-stack-detection/scripts/detect_stack.py`,
  `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py`, `$AUDIT_CORE_ROOT/skills/audit-finding-writer/scripts/findings.py`;
  imported: `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/repo_walk.py`, `$AUDIT_CORE_ROOT/skills/audit-sensitive-data-catalog/scripts/catalog.py`.
- `evals/` - sample repo planting a table without PK, a float money column, an unindexed FK, and an EF migration with an empty `Down()`; `evals.json` describes the expected result.
