# Node / Express (Prisma, TypeORM, Sequelize, Knex, Mongoose) reference for audit-db-schema

## Stack markers
`package.json` with `prisma`/`@prisma/client`, `typeorm`, `sequelize`, `knex`, `drizzle-orm`, `mongoose`. NestJS uses TypeORM or Prisma most often. Mongoose = document store: keys/indexes still apply, FKs and migrations mostly do not (see false positives).

## Where the relevant code lives
- Prisma: `prisma/schema.prisma`, `prisma/migrations/<ts>_<name>/migration.sql`, `prisma/seed.ts`.
- TypeORM: `src/**/*.entity.ts`, `src/migrations/<ts>-<Name>.ts` (`up`/`down`), `ormconfig`/`DataSource` (`synchronize: true` is a finding in prod).
- Sequelize: `models/*.js`, `migrations/<ts>-<name>.js` (`up`/`down`), `seeders/`.
- Knex: `knexfile.js`, `migrations/<ts>_<name>.js` (`exports.up`/`exports.down`), `seeds/`.
- Drizzle: `src/db/schema.ts`, `drizzle/*.sql` (forward-only by design).
- Loose DDL: `db/*.sql`, `docker-entrypoint-initdb.d/*.sql`.

## Dangerous / interesting APIs and patterns
- Prisma: `price Float`, `total Float` - use `Decimal @db.Decimal(18, 4)`; `createdAt DateTime` is `timestamp(3)` **without** zone on Postgres unless `@db.Timestamptz`; `name String` is `text` (unbounded) unless `@db.VarChar(n)`; relation fields (`@relation(fields: [customerId], references: [id])`) get **no index** on Postgres/SQL Server unless `@@index([customerId])`; `onDelete: Cascade` on relations to shared models; model without `@id`/`@@id`; `@updatedAt` present but no `createdBy`.
- TypeORM: `@Column('float'|'double'|'real')` for money, `@Column({ type: 'decimal' })` without `precision/scale` (defaults to `decimal(10,0)` on some drivers - integers!); `@Column()` on a `string` -> `varchar(255)`; `@Column({ type: 'timestamp' })` vs `timestamptz`; `@ManyToOne` without `@Index()` on the join column; `onDelete: 'CASCADE'`; no `@VersionColumn`; `@DeleteDateColumn` soft delete without an index; `synchronize: true`; migration `down()` empty or `throw new Error('not implemented')`.
- Sequelize: `DataTypes.FLOAT|DOUBLE` for money, `DataTypes.STRING` unbounded (`STRING(n)` is bounded), `DataTypes.DATE` (tz-aware on Postgres, naive on MySQL), `references` without `indexes`, `sequelize.sync({ force: true })`, migration `down: async () => {}`.
- Knex: `table.float('price')`, `table.decimal('price')` (default `(8,2)` - too small), `table.string('name')` (255 default, fine) vs `table.text()`, `table.timestamp('created_at')` vs `table.timestamp('created_at', { useTz: true })`, `.references('id').inTable('customers')` without `.index()`, `.onDelete('CASCADE')`, `exports.down` missing/empty, `table.dropColumn` in `up`.
- Mongoose: no `schema.index()` on queried fields, `unique: true` without `sparse` on optional fields, `Number` for money (use `mongoose.Types.Decimal128`), no `timestamps: true`, plaintext `password` field without pre-save hash.
- Seeds inserting real-looking emails/phones/hashes.
- JS `number` for 64-bit ids (`BigInt` columns) - precision loss above 2^53; Prisma `BigInt` maps to `bigint` in JS, TypeORM returns strings.

## What "good" looks like
```prisma
model OrderLine {
  id         Int      @id @default(autoincrement())
  orderId    Int
  order      Order    @relation(fields: [orderId], references: [id], onDelete: Cascade)
  productId  Int
  product    Product  @relation(fields: [productId], references: [id], onDelete: Restrict)
  unitPrice  Decimal  @db.Decimal(18, 4)
  sku        String   @db.VarChar(64)
  createdAt  DateTime @default(now()) @db.Timestamptz(3)
  deletedAt  DateTime? @db.Timestamptz(3)
  @@index([orderId])
  @@index([productId])
  @@unique([sku, deletedAt])
}
```
Knex migration: `exports.up` adds, `exports.down` mirrors every change in reverse order, tested with `knex migrate:rollback`.

## Manual trace checklist
1. Build the table list from the latest migration state, not from models alone; `synchronize`/`sync` in prod means the DB may differ from any file.
2. Money models: `Decimal`/`decimal(p,s)` in schema **and** `Prisma.Decimal`/`string` handling in code (not `parseFloat`).
3. Hot queries (`findMany({ where, orderBy })`, `createQueryBuilder().where()`, `knex('t').where()`) -> matching `@@index`/`@Index`/`table.index`.
4. Delete flow: `delete()` vs `update({ deletedAt })`; do queries filter `deletedAt: null` everywhere (Prisma middleware/extension)?
5. `npx prisma migrate diff --from-migrations prisma/migrations --to-schema-datamodel prisma/schema.prisma` (read-only) to detect schema/migration drift; `typeorm migration:generate --check` equivalent.
6. Sensitive columns: `password` hashed with bcrypt/argon2 before save; tokens hashed; `ssn`/`cardNumber` absent or encrypted.

## Stack-specific false positives
- Prisma/Drizzle migrations are forward-only by design; the finding is "no documented rollback procedure", not "missing down()". Downgrade if a restore/forward-fix runbook exists.
- Mongoose documents do not have FKs; skip FK checks, keep index/type/sensitive checks.
- `Float` for geo coordinates, weights, percentages not summed into money.
- TypeORM `@CreateDateColumn`/`@UpdateDateColumn` count as audit columns.

## Tooling
- `npx prisma migrate diff ...` (above), `npx prisma validate`, `npx prisma db pull --print` against a read-only DB to dump live schema.
- `npx typeorm schema:log -d src/data-source.ts` prints the DDL diff between entities and DB without applying.
- `npx knex migrate:status`, `npx sequelize-cli db:migrate:status`.
- Postgres: `pg_stat_user_indexes`, `pg_indexes`; MySQL: `SHOW INDEX FROM t`.

## References
- Prisma docs: Data model (indexes, referential actions), Migrate (down migrations); TypeORM: Entities, Migrations, Indices; Knex: Schema Builder; Mongoose: Indexes.
- CWE-682, CWE-311, CWE-916, CWE-20; ASVS 2.4, 6.2, 8.3.
