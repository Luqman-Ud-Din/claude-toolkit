# .NET / C# reference for audit-report-generator

What the report should say, enumerate and translate when the audited backend is ASP.NET
Core. The generator is stack-agnostic; this file is for the reviewer who fills the
scope table, checks the top-three wording and writes the remediation plan in terms the
team's engineers recognise.

## Stack markers
`*.sln`, `*.csproj`, `Program.cs`, `appsettings*.json`, `ocelotconfig.json` (Ocelot gateway),
`Migrations/` (EF Core), `Hangfire` registrations. Note microservice layout in the scope
table: one row per service is clearer than "the backend".

## Where the relevant code lives (what "Scope" must enumerate)
- Solution and projects: list every `*.csproj` that ships (MicroAPI, WebHost/gateway, background hosts).
- Entry points: controllers under `Controllers/`, minimal API `Map*` calls, Hangfire jobs, SignalR hubs, gRPC services.
- Config surfaces: `appsettings.{Environment}.json`, environment variables, Key Vault references, `launchSettings.json` (dev only - say so).
- Data: each `DbContext`, connection strings per tenant (multi-tenant apps: say whether tenant switching was in scope).
- Out-of-repo pieces to list under "Not checked" when absent: IIS/nginx config, Azure App Service settings, Docker compose for prod.

## Findings that are typical launch blockers in this stack (and how to phrase them)
| Engineering finding | Executive wording for "Top three risks" |
|---|---|
| `[AllowAnonymous]` on an admin/tenant controller | "Anyone on the internet can call administrative functions without logging in." |
| Missing `CompanyId`/`BranchId` filter, static `CustomConnectionString` not set per request | "One customer can see or change another customer's records." |
| `FromSqlRaw($"...")` with interpolation | "A crafted search string can read or delete the whole database." |
| JWT key / connection string in `appsettings.Production.json` | "Anyone with repository access can impersonate any user or connect to the production database." |
| `TokenValidationParameters` with `ValidateLifetime=false` | "Stolen login tokens never expire." |
| `UseDeveloperExceptionPage()` unconditional | "Error pages reveal internal code and configuration to visitors." |

## What "good" looks like (remediation plan wording)
Write fixes in the team's idiom so the table is actionable without re-reading the finding:
- "Add `[Authorize(Roles = CustomRoles.SuperAdmin)]` to `CompanyAdminController`; add a 401 integration test."
- "Move the tenant filter into `RepositoryBaseManager<T>` with `HasQueryFilter`, so every query inherits it."
- "Replace `FromSqlRaw` interpolation with `FromSqlInterpolated`."
- "Move `Jwt:Key` to Key Vault / environment; rotate; purge history with `git filter-repo`."
- "Add `app.UseHsts()` outside the Development branch."
Group by file or project: one `Program.cs` ticket for all pipeline/header items, one base-repository ticket for all tenant-filter items (shared `root_cause_key`).

## Report review checklist (manual trace)
1. Scope table names every shipping project; gateway (`WebHost`) is listed separately from the services it fronts.
2. Every Critical/High points at a file that exists in the solution; no finding cites `bin/` or `obj/`.
3. Multi-tenant apps: the summary says explicitly whether cross-tenant access was tested (`audit-multi-tenant-isolation` row).
4. Background jobs (Hangfire) and gateway routes (Ocelot) appear in the scope table as checked or not checked.
5. Evidence appendix includes command output (`dotnet list package --vulnerable`, `curl -I`) rather than only code snippets where a skill ran tools.

## Stack-specific false positives (do not let these become launch blockers)
- `[AllowAnonymous]` on `/health`, `/login`, `/register`, `/forgot-password`.
- `FromSqlRaw("... {0}", id)` with positional parameters.
- `HttpClient` created inside `AddHttpClient<T>()` registrations.
- Missing HSTS in a service that only sits behind a TLS-terminating gateway which sets it (cite the gateway config; downgrade to Low).
- `IsDeleted == false` conventions: soft delete not enforced is Medium at most unless a finding shows data returned to another tenant.

## Tooling (evidence to expect in Appendix B)
`dotnet list package --vulnerable --include-transitive`, `dotnet build -warnaserror` output,
SecurityCodeScan / Roslyn analyzer summaries, `curl -sI https://host` header dumps,
`dotnet-counters` snapshots for leak findings. Export: `pandoc audit/audit-report.md -o audit/audit-report.docx --toc --from gfm` (Word is the usual format for .NET shops).

## References
ASP.NET Core security docs (Enforce HTTPS, Authorization, Data protection, Safe storage of app secrets);
OWASP ASVS 4.0.3 V4, V5.3, V14.4; CWE-306, CWE-639, CWE-89, CWE-798, CWE-319.
