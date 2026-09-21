# Migration hygiene: reversibility, data loss, sync, seed data

`scripts/migration_reversibility.py` grades each migration file; this document
says what each grade means and how to fix it per tool.

## Grades

| Grade | Meaning | Severity guide |
|---|---|---|
| `reversible` | a reverse step exists and mirrors the forward step | - |
| `irreversible` | reverse step missing, empty, `pass`, `noop`, or throws | Medium; High if the forward step is destructive or the release has no restore runbook |
| `data-loss` | forward step drops a table/column, narrows a type, deletes/updates rows | Critical if shipped in the same release as the code change without a backup step; High otherwise |
| `raw-sql` | forward step contains hand-written SQL - review by hand, the tool cannot reverse it | Info unless it is also data-loss |
| `seed-pii` | seed/data step contains values that look like real emails, phone numbers, password hashes, card numbers | High |
| `initial` | first migration; missing reverse is usually acceptable | Info |

## Per tool

### EF Core (`Migrations/*.cs`)
- Reverse: `protected override void Down(MigrationBuilder migrationBuilder)`. Empty body, only comments, or `throw new NotSupportedException()` = irreversible.
- Data loss: `DropTable`, `DropColumn`, `AlterColumn` with a smaller `maxLength`/narrower type, `migrationBuilder.Sql("DELETE|UPDATE|TRUNCATE ...")`.
- Seed: `migrationBuilder.InsertData(...)`, `HasData(...)` in the snapshot.
- Sync: `dotnet ef migrations has-pending-model-changes` (EF 8+); on older versions run `dotnet ef migrations add __check --dry-run` on a scratch copy (never in the audited repo) or compare the snapshot with entities by hand.
- Good pattern: expand (add nullable column + backfill), deploy code, contract (make NOT NULL / drop old) in a later release. Custom operations via `migrationBuilder.Sql` should have a paired reverse SQL in `Down`.

### Flyway (`db/migration/V*__*.sql`)
- Reverse: `U<version>__<desc>.sql` undo scripts (Teams feature; Community users write them but must apply by hand) - absence is the norm, so the finding is "no rollback procedure" unless a forward-fix + backup policy is documented.
- Data loss: `DROP TABLE|COLUMN`, `ALTER TABLE ... ALTER|MODIFY COLUMN` narrowing, `DELETE`/`UPDATE` without `WHERE`, `TRUNCATE`.
- Sync: `flyway validate` (checksum) plus `ddl-auto=validate` on a scratch DB.
- `R__` repeatable migrations must be idempotent (`CREATE OR REPLACE`).

### Liquibase (`db/changelog/*.xml|yaml|sql`)
- Reverse: `<rollback>` element / `rollback:` key / `-- rollback` comment in formatted SQL. Auto-rollback exists for `createTable`, `addColumn`, `createIndex`, `addForeignKeyConstraint`, `renameColumn`, `renameTable`, `addUniqueConstraint`; **not** for `sql`, `dropTable`, `dropColumn`, `update`, `delete`, `insert`, `loadData`, `modifyDataType`.
- Data loss: `dropTable`, `dropColumn`, `modifyDataType`, `delete`, `update`, raw `sql`.
- Sync: `liquibase diff` against a scratch DB built from the changelog; `liquibase status`.

### Django (`<app>/migrations/*.py`)
- Reverse: `RunPython(forward, reverse_code=...)` - missing or `RunPython.noop` without justification = irreversible; `RunSQL(sql, reverse_sql=...)` same. Schema operations (`AddField`, `CreateModel`) reverse automatically; `RemoveField`/`DeleteModel` reverse structurally but the data is gone.
- Data loss: `RemoveField`, `DeleteModel`, `AlterField` narrowing `max_length` or changing type, `RunSQL` with `DELETE|UPDATE|DROP`.
- Sync: `manage.py makemigrations --check --dry-run`.
- Seed: fixtures `*.json|yaml`, `RunPython` inserting rows.

### Alembic (`alembic/versions/*.py`)
- Reverse: `def downgrade(): pass` or `raise` = irreversible.
- Data loss: `op.drop_table`, `op.drop_column`, `op.alter_column(type_=...)`, `op.execute("DELETE|UPDATE")`.
- Sync: `alembic check` (1.9+).

### Knex (`migrations/*.js|ts`)
- Reverse: `exports.down` / `export async function down` missing, empty, or `return Promise.resolve()`.
- Data loss: `dropTable`, `dropColumn`, `table.dropColumns`, `knex.raw('DELETE|DROP|ALTER ... DROP')`.
- Sync: none built in; entity definitions live in code - compare by hand.

### TypeORM (`src/migrations/*.ts`) and Sequelize (`migrations/*.js`)
- Reverse: `public async down(queryRunner)` / `down: async (queryInterface)` empty or throwing.
- Data loss: `DROP`, `dropTable`, `removeColumn`, `changeColumn` narrowing.
- Sync: `typeorm schema:log` / `migration:generate` producing a non-empty diff.

### Prisma (`prisma/migrations/*/migration.sql`) and Drizzle (`drizzle/*.sql`)
- Forward-only by design; no down script exists. Grade every migration `irreversible` with the note "tool is forward-only; require a tested restore or forward-fix procedure" and rate once as one finding, not per file.
- Data loss: `DROP TABLE|COLUMN`, `ALTER COLUMN ... TYPE`, Prisma warning comments `/* Warnings: ... data will be lost */` inside the migration file - grep for `Warnings:`.
- Sync: `prisma migrate diff --from-migrations ... --to-schema-datamodel ...`.

## Seed-data PII used by the script
Values come from `audit-sensitive-data-catalog` (`find_values` limited to `V-EMAIL`,
`V-PASSWORD-HASH`, `V-PHONE`, `V-IBAN`, `V-CARD`); add formats to the catalog, not the script.
- Email addresses that are not placeholders (example and test domains, fixture mailboxes such
  as `test@` or `john.doe@`) and not role mailboxes (`admin@`, `noreply@`, `support@`, `info@`).
- Phone-number shaped strings.
- Password hashes: bcrypt, argon2, `pbkdf2_sha256$`, ASP.NET Identity (`AQAAAA...`).
- Luhn-valid card numbers that are not published test cards, and IBAN shapes (no mod-97 filter).
- Overlapping values report once: digits inside an IBAN are not also reported as a card.
Everything the script flags is a candidate; open the file and decide.
