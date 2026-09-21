# .NET / C# reference for audit-test-coverage-and-ci

## Stack markers

`*.sln`, `*.csproj`. Test projects: `<IsTestProject>true</IsTestProject>` or package
references to `xunit`, `NUnit`, `MSTest.TestFramework`, plus `Microsoft.NET.Test.Sdk`.
Integration: `Microsoft.AspNetCore.Mvc.Testing` (`WebApplicationFactory<T>`),
`Testcontainers.*` (`MsSql`, `PostgreSql`, `Redis`), `Respawn` (DB reset). E2E:
`Microsoft.Playwright`, `Selenium.WebDriver`, SpecFlow/Reqnroll. A solution with **no**
test project at all (common in this family of repos) is a High finding on its own.

## Where the relevant code lives

`tests/**`, `*.Tests/`, `*.IntegrationTests/`, `*.UnitTests/`; `Directory.Build.props`
(analyzers, `TreatWarningsAsErrors`); `coverlet.runsettings` / `.runsettings`;
`.github/workflows/*.yml`, `azure-pipelines.yml` (`DotNetCoreCLI@2` with `command: test`);
`global.json` (SDK pin), `packages.lock.json` (`RestorePackagesWithLockFile`).
Production units to map: `Controllers/*Controller.cs`, `*Manager.cs`, `*Service.cs`,
`*Handler.cs` (MediatR), `BackgroundJobs/*`, `*Repository.cs`, `DbContext` query filters.

## Dangerous / interesting APIs and patterns

- Skipped: `[Fact(Skip = "...")]`, `[Theory(Skip = "...")]`, `[Ignore]` / `[Ignore("...")]`
  (NUnit/MSTest), `[Explicit]` (NUnit, never runs in CI), `[Trait("Category","Manual")]`
  filtered out by `--filter`; `Assert.Inconclusive()`; `return;` at the top of a test body.
- In-memory substitutes for a relational DB: `UseInMemoryDatabase(`, `UseSqlite("DataSource=:memory:")`
  when production is SQL Server - the provider ignores constraints, collation, transactions
  and raw SQL, so `FromSqlRaw`/stored procedures/tenant query filters are never exercised.
- Tests that touch a shared/prod database: connection strings with `Server=` and a real host in
  `appsettings.Test.json` or hard-coded in tests; `Database.EnsureDeleted()` on a named server.
- Hygiene: `Thread.Sleep(` / `Task.Delay(` for timing, `.Result`/`.Wait()` deadlock-prone waits,
  `static` mutable fixtures, tests depending on order (`[Collection]` misuse, `TestCaseOrderer`),
  `DateTime.Now` in assertions, random data without a seed (Bogus without `Randomizer.Seed`).
- No auth tests: no test creates a `ClaimsPrincipal`/JWT with a *different* role or tenant and
  asserts 403/404; `WebApplicationFactory` tests that always call `AllowAnonymous` endpoints.
- CI: `dotnet test` missing, or run with `|| true`, `continueOnError: true`, `--filter` excluding
  everything, `-p:SkipTests=true`; `dotnet build` without `-warnaserror` and no analyzers;
  no `dotnet list package --vulnerable`; no `dotnet format --verify-no-changes`.
- Reproducibility: no `global.json`, no `packages.lock.json` with `--locked-mode`, floating
  `Version="*"`, `Directory.Packages.props` absent; artifacts published without a version
  (`-p:Version=`, GitVersion/MinVer/Nerdbank.GitVersioning) or signature (`signtool`, `dotnet nuget sign`).

## What "good" looks like

```csharp
// Integration test against a real SQL Server in a container
public sealed class ApiFixture : IAsyncLifetime
{
    public MsSqlContainer Db { get; } = new MsSqlBuilder().Build();
    public WebApplicationFactory<Program> Factory { get; private set; } = default!;
    public async Task InitializeAsync()
    {
        await Db.StartAsync();
        Factory = new WebApplicationFactory<Program>().WithWebHostBuilder(b =>
            b.ConfigureAppConfiguration((_, c) => c.AddInMemoryCollection(new Dictionary<string, string?>
                { ["ConnectionStrings:Master"] = Db.GetConnectionString() })));
    }
    public async Task DisposeAsync() => await Db.DisposeAsync();
}
[Fact] public async Task Customer_cannot_read_other_tenants_order()
{
    var client = Factory.CreateClientAs(tenant: "B", role: "Customer");
    var res = await client.GetAsync("/api/orders/123");   // order 123 belongs to tenant A
    res.StatusCode.Should().Be(HttpStatusCode.NotFound);
}
```
```yaml
# CI (GitHub Actions)
- run: dotnet restore --locked-mode
- run: dotnet build --no-restore -c Release -warnaserror
- run: dotnet test --no-build -c Release --logger trx --collect:"XPlat Code Coverage" --results-directory TestResults
- run: dotnet list package --vulnerable --include-transitive | tee vuln.txt && ! grep -q "has the following vulnerable" vuln.txt
```
Coverage gate: `coverlet.collector` + `ReportGenerator` with `-p:Threshold=80 -p:ThresholdType=line`
scoped to the critical projects, or `dotnet-coverage` + `--fail-below`.

## Manual trace checklist

1. Auth: open `AuthController`/token service tests. Is there a test for an expired token, a
   wrong role, a wrong tenant? If tests only cover successful login, mark the path *partial*.
2. Money: `*Payment*`, `*Invoice*`, `*Voucher*`, `*Ledger*`, `*Price*` managers - tests with
   rounding, negative/zero, currency, and a failing gateway?
3. Data mutation: the biggest `*Manager` (orders, stock): tests run against SQL Server (container)
   or `InMemoryDatabase`? Tenant/branch filter asserted?
4. Background jobs (`Hangfire` classes): any test at all?
5. CI: the PR workflow's step list; `dotnet test` present, not filtered, not `continueOnError`.

## Stack-specific false positives

- `[Fact(Skip = "...")]` inside a `#if DEBUG` block or a sample project: not CI-relevant.
- `UseInMemoryDatabase` in a *unit* test of pure business logic with no SQL: acceptable; the
  finding is about *integration* tests using it as the only DB test.
- `[Trait("Category", "Integration")]` filtered out in the PR job but run in a nightly job:
  partial, not fail - cite the nightly job.
- Test projects present but not referenced by the `.sln`: `dotnet test <sln>` will not run
  them - that is a finding, not a false positive.

## Tooling

`dotnet test --list-tests` (inventory), `dotnet test --collect:"XPlat Code Coverage"` +
`reportgenerator -reports:**/coverage.cobertura.xml -targetdir:audit/evidence/... -reporttypes:MarkdownSummary`,
`dotnet list package --vulnerable`, `dotnet format --verify-no-changes`, Stryker.NET for
mutation score on the money path (`dotnet stryker --project Inventory.Api.csproj`).

## References

- xUnit skip: https://xunit.net/docs/comparisons; NUnit `[Ignore]`/`[Explicit]`; MSTest `[Ignore]`.
- Testcontainers for .NET: https://dotnet.testcontainers.org
- Integration tests in ASP.NET Core: https://learn.microsoft.com/aspnet/core/test/integration-tests
- CWE-1120 (excessive complexity untested), CWE-1127 (compilation with insufficient warnings), ASVS-1.14.4, ASVS-14.1.x.
