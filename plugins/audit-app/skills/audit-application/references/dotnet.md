# .NET / C# reference for audit-application

What the orchestrator needs to know about a .NET codebase before it plans and runs
the children. Topic detail lives in each child's own `references/dotnet.md`.

## Stack markers

- `*.csproj`, `*.sln`, `*.fsproj` (detect_stack id `dotnet`).
- `Sdk="Microsoft.NET.Sdk.Web"`: an HTTP service, so every backend child applies.
  `Microsoft.NET.Sdk.Worker`: a background worker only, where api-contract and headers have
  little to review. `Microsoft.NET.Sdk.Razor`, `Views/**/*.cshtml`, `Pages/**/*.cshtml`:
  server-rendered HTML. `*.razor`: Blazor.
- Gateways: `ocelot*.json` (Ocelot) or `ReverseProxy` sections (YARP). The system is several
  services behind one entry point. Pass every service root to the children and keep the
  gateway in scope for authz and headers.

## Where the relevant code lives

- The `.sln` lists the projects; read it first to name every shipping service in the scope.
- Per service: `Program.cs` / `Startup.cs` (pipeline, DI, auth), `appsettings*.json`,
  `Properties/launchSettings.json` (local URLs and ports), `Controllers/`,
  `*DbContext.cs`, `Migrations/` (often absent when schema is managed elsewhere),
  `BackgroundJobs/` / Hangfire / Quartz / `IHostedService` registrations.
- Tests: `*.Tests.csproj` / `*.IntegrationTests.csproj`. No test projects is itself a result
  for test-coverage, not a reason to skip it.

## Dangerous / interesting APIs and patterns

These are the signals to read during setup. They decide questions and applicability; they
are not findings.

- **Multi-tenant hints:** `HasQueryFilter(` on tenant columns, `TenantId`/`CompanyId`/
  `OrganizationId` on entities, tenant id read from claims (`User.FindFirst("CompanyId")`),
  per-request connection strings or database names (a static `CustomConnectionString.DbName`
  set in controller constructors), `Finbuckle.MultiTenant`. Any of these warrant the
  multi-tenant question being asked with the hint shown.
- **Background work:** Hangfire, Quartz, `BackgroundService`, `System.Threading.Timer`. Make
  sure concurrency and datetime are in scope (duplicate job runs, cron zones) and tell
  leak and async about them.
- **Real-time:** SignalR hubs. frontend-memory-leak pairs them with client subscriptions.
- **Integrations:** `HttpClient`, `IHttpClientFactory`, SDKs for payment, tax, SMS and storage.
  These feed the privacy mapper (third parties) and performance (timeouts).

## What "good" looks like

A .NET repo that is ready to audit without "limited access" gaps:

- The SDK in `global.json` (or the `TargetFramework`) is installed: `dotnet --list-sdks`.
- `dotnet restore` has run, so `obj/project.assets.json` exists. dependency-vulnerabilities
  needs it for `dotnet list package --vulnerable`; the child never restores by itself.
- `dotnet build -c Release` succeeds. Analyzers and the test suite can run.
- A read-only connection string to a non-production database (db-schema live dump, ORM query
  log), or migrations in the repo.
- A test environment URL with two user accounts (authz probe) and two tenants (tenant probe).
  A staging URL for live headers.
- A full git clone, not shallow: secrets history scan and technical-debt churn.

## Manual trace checklist

Prerequisites to confirm at setup, in this order. Each names the children it unlocks and
what to record when it is missing.

1. SDK installed and `dotnet build` possible -> test-coverage (run suite), technical-debt
   (analyzers). Missing: `--limited "build not possible: <error>"`.
2. Packages restored or restorable -> dependency-vulnerabilities, licensing (licence metadata
   from `~/.nuget/packages`). Missing: `--limited "no restore; NuGet vulnerability data not collected"`.
3. Read-only DB access or migrations present -> db-schema, orm, concurrency (unique
   constraints, rowversion). Missing: `--limited "schema from entity classes only"`.
4. Test URL + two user tokens -> authz probe. Two tenants -> multi-tenant probe. Staging URL
   -> headers live check. Running instance -> backend-resource-leak and performance load tests.
   Missing: `--limited "no test URL; dynamic probe not run"`.
5. Git history depth: `git rev-parse --is-shallow-repository`. Shallow -> secrets and
   technical-debt limited.
6. Gateway config present (`ocelot*.json`): confirm which routes are public. Otherwise authz
   records the gateway as not checked.

## Stack-specific false positives

Wrong applicability calls to avoid:

- **API-only .NET repo:** frontend-best-practices, frontend-memory-leak and client-auth are
  genuinely n/a. XSS and accessibility are n/a **only if** there are no `.cshtml`/`.razor` files
  (`plan.py` checks). A Razor login page or Swagger UI customisation brings XSS back in.
- **Blazor WebAssembly** has no `package.json`, so detect_stack reports no frontend. The
  frontend children have no Blazor reference file. Keep XSS and accessibility (templates), and
  run client-auth through `--skill` if tokens are stored in the browser (`localStorage` via
  `Blazored.LocalStorage`).
- **No `Migrations/` folder** does not mean no schema. db-schema still runs from the entity
  classes and `OnModelCreating`; record that the migration history is outside the repo.
- **`[AllowAnonymous]` health endpoints** are not a reason to rate authz differently at setup.
  Leave it to the child.

## Tooling

```bash
dotnet --list-sdks
dotnet restore <Solution>.sln                    # user-approved; creates obj/, does not change source
dotnet build <Solution>.sln -c Release
dotnet list <Solution>.sln package --vulnerable --include-transitive
dotnet list <Solution>.sln package --outdated
dotnet test <Solution>.sln --collect:"XPlat Code Coverage"
dotnet ef dbcontext info --project <Api>.csproj  # only if dotnet-ef is installed; never "migrations add"
git rev-parse --is-shallow-repository
```

Restore and build write `obj/`/`bin/` only. Still ask before running them in the user's
working tree, and prefer a scratch clone for anything that installs tools.

## Child applicability for .NET repos

| Repo shape | n/a children (skipped with `skip_kind: n/a`) |
|---|---|
| API / services only | frontend-best-practices, frontend-memory-leak, client-auth-and-storage; XSS and accessibility unless Razor/Blazor files exist |
| Worker only | as above, plus expect api-contract and security-headers to record "no HTTP surface" |
| Services + separate SPA repo | none, but pass both roots, since frontend children need the SPA root |

## References

- Child references: `../audit-authz-and-access-control/references/dotnet.md`,
  `../audit-multi-tenant-isolation/references/dotnet.md`, `../audit-db-schema/references/dotnet.md`.
- `audit-finding-writer/references/findings-schema.md` (prefixes, paths).
- Microsoft docs: ASP.NET Core security, EF Core global query filters, `dotnet list package`.
