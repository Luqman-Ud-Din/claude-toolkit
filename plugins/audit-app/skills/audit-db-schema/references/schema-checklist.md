# Per-table schema checklist and engine notes

Use this as the rubric behind the "Table-by-table checklist" in the report. The
script `scripts/schema_checklist.py` fills in what it can parse; the rest is
manual. Every "no" is a candidate finding; group by root cause.

## Checklist

| # | Item | Pass when | Typical severity when failed |
|---|---|---|---|
| 1 | Primary key | every table written by the app has a PK (heap tables fail); PK is stable (not email, not a mutable code) | High (no PK: duplicates, no replication/CDC, no ORM updates) |
| 2 | Foreign keys | every `*Id`/`*_id` column that references another table has an FK constraint | Medium (orphans) / High when the orphan breaks money or tenancy |
| 3 | Cascade rules | CASCADE only parent -> owned child; RESTRICT/NO ACTION toward shared reference data; SET NULL only on nullable audit refs | High (accidental mass delete) |
| 4 | FK indexes | every FK column is the leading column of some index (Postgres, SQL Server, Oracle, SQLite do not auto-create; MySQL InnoDB does) | High on hot tables, Medium elsewhere |
| 5 | Query indexes | filtered/sorted columns of list endpoints covered by a composite index in `WHERE`-equality, then range, then `ORDER BY` order | High on main lists |
| 6 | Redundant indexes | no index that is a left-prefix of another; no duplicate definitions; no unused indexes (needs live stats) | Low (write cost) |
| 7 | Money type | `decimal(p,s)`/`numeric`, s >= 2 for currency, 4-6 for rates/unit costs; never float/real/double; currency code stored alongside for multi-currency | Critical in ledgers/invoices, High elsewhere |
| 8 | Timestamps | zone-aware type (`datetimeoffset`, `timestamptz`) or documented UTC with enforcement in the ORM | High when timestamps drive cut-offs, billing, or audit; Medium otherwise |
| 9 | String bounds | names, codes, emails, phones bounded (`nvarchar(n)`); free text may be unbounded | Medium (index/row bloat, DoS via 2 GB rows) |
| 10 | Nullability | NOT NULL where the business requires a value; no magic defaults (`''`, `0`, `1900-01-01`) standing in for null | Medium |
| 11 | Unique constraints | natural keys (code per tenant, email per tenant, SKU per company) unique; filtered for soft delete | High (duplicates in money or identity) |
| 12 | Check constraints | quantities/prices >= 0, status in the allowed set, date ranges ordered | Medium |
| 13 | Naming | one case convention, FK named `<Table>Id`/`<table>_id`, index names `IX_<table>_<cols>` | Low |
| 14 | Audit columns | `CreatedAt`, `CreatedBy`, `UpdatedAt`, `UpdatedBy` on every business table; populated by the ORM, not by hand | Medium (Low on pure lookup tables) |
| 15 | Soft delete | one convention (`IsDeleted` or `DeletedAt`), global query filter in the ORM, filtered unique indexes, index on the flag when tables are large, a purge policy | High when the filter is by convention only |
| 16 | Sensitive columns | passwords hashed (Argon2id/bcrypt/PBKDF2), tokens hashed or short-lived, PAN/national id/bank data encrypted or tokenised, documented column list | Critical (plaintext passwords/PAN), High (other PII) |
| 17 | Concurrency token | `rowversion`/`@Version`/`xmin`/`version` on rows edited by users concurrently (stock, balances, documents) | Medium (lost updates) / High for stock and money |
| 18 | Migrations reversible | every migration has a working reverse (Down/undo/reverse_code) or a documented forward-fix + restore procedure | High for destructive migrations, Medium otherwise |
| 19 | No data loss | destructive steps (drop column/table, type narrowing) are preceded by a backup/copy step and shipped in a later release than the code that stops using the column (expand/contract) | Critical |
| 20 | Model in sync | ORM model == last migration state (`has-pending-model-changes`, `makemigrations --check`, `prisma migrate diff`) | High (next deploy generates surprise DDL) |
| 21 | No PII in seed | seed/fixture data uses obviously synthetic values | High (real people in every dev DB) |
| 22 | Tenant columns | `CompanyId`/`TenantId` present, NOT NULL, leading column in indexes, part of unique constraints | owned by `audit-multi-tenant-isolation`; record here, delegate |

## Engine notes

| Concern | SQL Server | PostgreSQL | MySQL/MariaDB | SQLite |
|---|---|---|---|---|
| Money | `decimal(18,4)`; `money` type is discouraged (rounding on divide) | `numeric(18,4)`; `money` type locale-bound | `DECIMAL(18,4)` | `NUMERIC`/`INTEGER` minor units |
| Timestamps | `datetimeoffset(3)`; `datetime` has 3.33 ms precision and no zone | `timestamptz` | `TIMESTAMP` converts via session zone (fragile); `DATETIME` naive - store UTC | `TEXT` ISO 8601 UTC |
| Unbounded string | `nvarchar(max)` - not indexable, off-row | `text` - indexable but unbounded; use `varchar(n)` or CHECK | `TEXT` - prefix index only | all `TEXT` |
| FK index | not automatic | not automatic | automatic (InnoDB) | not automatic |
| Filtered unique | `CREATE UNIQUE INDEX ... WHERE IsDeleted = 0` | partial index `WHERE deleted_at IS NULL` | not supported - use generated column trick | partial index supported |
| Concurrency | `rowversion` | `xmin` system column or `version int` | `version int` | `version int` |
| Missing-index hints | `sys.dm_db_missing_index_details` | `pg_stat_user_tables.seq_scan` vs `idx_scan` | `sys.schema_unused_indexes`, slow log | `EXPLAIN QUERY PLAN` |

## Index design rules (for the "Recommended indexes" table)

1. Start from the query, not the table: equality predicates first (most selective, tenant columns included), then range predicates, then `ORDER BY` columns in the same direction.
2. One composite index beats several single-column indexes for the same query; single-column FK indexes remain useful for joins and cascades.
3. Include columns (`INCLUDE (...)` / covering) only for the top 2-3 hottest queries; every index costs writes.
4. Do not recommend an index on a column with 2-3 distinct values alone (`IsDeleted`, `Status`) unless filtered or as a trailing column.
5. For each recommendation cite the code path (`Manager.Method` -> LINQ/SQL) so the developer can measure before/after with `EXPLAIN`/`SET STATISTICS IO`.
6. Flag redundancy: `IX_A (CompanyId)` is redundant when `IX_B (CompanyId, BranchId)` exists and both are non-unique.
