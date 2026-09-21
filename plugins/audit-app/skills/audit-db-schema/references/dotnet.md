# .NET / EF Core reference for audit-db-schema

## Stack markers
`*.csproj` with `Microsoft.EntityFrameworkCore.*` (SqlServer, Npgsql, Pomelo MySql, Sqlite). Variants: EF Core code-first with a `Migrations/` folder; database-first / "schema managed outside the repo" (no `Migrations/`, only `*DbContext.cs` + entities, and maybe loose `*.sql` scripts); Dapper with hand-written SQL (schema only visible in `.sql` files).

## Where the relevant code lives
- `*.Entity/` or `Data/`: `*DbContext.cs` (`OnModelCreating`), `Configurations/*Configuration.cs` (`IEntityTypeConfiguration<T>`), entity classes.
- `Migrations/`: `<timestamp>_<Name>.cs` (`Up`/`Down`), `<timestamp>_<Name>.Designer.cs`, `<Context>ModelSnapshot.cs` - the snapshot is the most complete single description of the schema.
- Loose DDL: `Scripts/`, `Database/`, `*.sql` anywhere in the solution; `.dacpac`/`.sqlproj` projects.
- Seed data: `HasData(...)` in `OnModelCreating`, `migrationBuilder.InsertData(...)`, `DbInitializer`/`Seed*.cs`.

## Dangerous / interesting APIs and patterns
- `public double|float Price|Amount|Total|Cost|Rate|Balance|Tax|Discount` - money in binary float (`decimal` is the only correct CLR type; column must be `decimal(p,s)`).
- `public decimal X` with no `HasPrecision`/`HasColumnType` - EF Core defaults to `decimal(18,2)`; fine for currency, wrong for exchange rates or unit costs with 4+ decimals.
- `public DateTime CreatedAt` mapped to `datetime`/`datetime2` - no zone; prefer `DateTimeOffset` -> `datetimeoffset`, or document UTC and enforce with a value converter.
- `public string Name` without `[MaxLength]`, `[StringLength]`, or `HasMaxLength` -> `nvarchar(max)` on SQL Server (cannot be indexed, bloats rows).
- `HasOne().WithMany().HasForeignKey()` without `.OnDelete(DeleteBehavior.Restrict|NoAction)` on references to shared tables (Company, Branch, Product); EF's default for required relationships is Cascade.
- `HasIndex` absent for a FK: EF Core creates an index for every FK automatically **only when the relationship is configured** (navigation or fluent). Shadow/int-only "FK" columns (`public int CategoryId` with no navigation and no `HasOne`) get **no FK and no index** - a common trap in this repo family.
- `[Timestamp] byte[] RowVersion` / `IsRowVersion()` / `IsConcurrencyToken()` absent on editable business rows.
- `Delete` in a base repository mapping to `Remove()` while entities carry `IsDeleted` - soft delete by convention only; check `HasQueryFilter(e => !e.IsDeleted)` exists and that unique indexes are filtered (`HasFilter("[IsDeleted] = 0")`).
- `migrationBuilder.Sql("...")` in migrations, `DropColumn`/`DropTable`/`AlterColumn` narrowing a type, `RenameColumn` done as drop+add.
- `protected override void Down(MigrationBuilder migrationBuilder) { }` - empty or throwing body.
- `HasData(new User { Email = "real.person@company.com", PasswordHash = ... })` - real PII/secrets in seed.
- `[Key]` missing and no `Id`/`<Type>Id` property, `HasNoKey()` / `.ToView()` used for tables that are written to.
- `UseSqlServer(..., o => o.CommandTimeout(...))` irrelevant here; `EnableSensitiveDataLogging` belongs to the logging audit.

## What "good" looks like
```csharp
public class OrderLineConfiguration : IEntityTypeConfiguration<OrderLine>
{
    public void Configure(EntityTypeBuilder<OrderLine> b)
    {
        b.ToTable("OrderLines");
        b.HasKey(x => x.Id);
        b.Property(x => x.UnitPrice).HasPrecision(18, 4);
        b.Property(x => x.Sku).HasMaxLength(64).IsRequired();
        b.Property(x => x.CreatedAt).HasColumnType("datetimeoffset");
        b.Property(x => x.RowVersion).IsRowVersion();
        b.HasOne(x => x.Order).WithMany(o => o.Lines).HasForeignKey(x => x.OrderId).OnDelete(DeleteBehavior.Cascade);
        b.HasOne(x => x.Product).WithMany().HasForeignKey(x => x.ProductId).OnDelete(DeleteBehavior.Restrict);
        b.HasIndex(x => new { x.CompanyId, x.BranchId, x.OrderId });
        b.HasIndex(x => x.Sku).IsUnique().HasFilter("[IsDeleted] = 0");
        b.HasQueryFilter(x => !x.IsDeleted);
    }
}
```

## Manual trace checklist
1. Open `*ModelSnapshot.cs` (or the DbContext if none) and list every `Entity(...)`; compare with `schema_checklist.py` output - anything the script missed goes in `not_checked`.
2. For each money-bearing entity (Sale, Purchase, Voucher, Ledger, Payment) confirm `decimal` + precision in **both** the property and the column type.
3. For the paginated list endpoints (`GetPaginationList` taking `DataTableAjaxPostModel`) read the `Where`/`OrderBy` in the manager and check a covering index exists for `(CompanyId, BranchId, <filter>, <sort>)`.
4. Trace one delete flow end to end: does `Delete` hit `Remove()` (hard) or set `IsDeleted`? Do child rows cascade? Is anything shared referenced with cascade?
5. Run `dotnet ef migrations list` and `dotnet ef migrations has-pending-model-changes` (EF 8+) if the project builds; a pending change means model and migrations are out of sync. If there is no `Migrations/` folder at all, record "schema managed outside repo; reviewed from entities and loose SQL only".
6. Check `Users`/`Tokens` tables: password column is a hash (`PasswordHash`, not `Password`), refresh tokens hashed or short-lived, no plaintext API keys.

## Stack-specific false positives
- `double` on quantities/weights/percentages that are not summed into money is acceptable; flag only when it feeds a total or a ledger.
- `DateTime` with a documented UTC convention and a `ValueConverter` setting `DateTimeKind.Utc` is Medium at most, not High.
- `OnDelete(Cascade)` from an aggregate root to its own child rows (Order -> OrderLines) is correct.
- Missing `Down()` on the **initial** migration is often deliberate (nothing to revert to); mention as Info.
- `HasData` with obviously synthetic values (`admin@example.com`, `test`) is fine.

## Tooling
- `dotnet ef migrations script --idempotent -o audit/evidence/audit-db-schema/full.sql` - full DDL for the parser when the project builds.
- `dotnet ef dbcontext script` (EF 5+) - DDL from the current model without migrations.
- `dotnet ef migrations has-pending-model-changes` - model/migration drift.
- SQL Server live (read-only): `SELECT * FROM sys.dm_db_missing_index_details`, `sys.dm_db_index_usage_stats` for unused indexes, `sp_BlitzIndex` if installed.
- Postgres live: `pg_stat_user_indexes` (idx_scan = 0 -> unused), `pg_stat_statements`.

## References
- EF Core docs: Indexes, Cascade delete, Concurrency tokens, Migrations (managing, custom operations).
- CWE-682 (incorrect calculation, float money), CWE-311/312 (missing encryption of sensitive data), CWE-916 (weak password hash), CWE-20 (missing constraints), ASVS 6.2 (algorithms), 8.3 (sensitive data at rest), 2.4 (credential storage).
