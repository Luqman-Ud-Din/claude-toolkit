# .NET / C# reference for audit-technical-debt

Where debt accumulates in .NET services, how it looks in the code, and which
analyzers measure it. Read with `scoring-and-prioritisation.md`; the scripts
already cover the language-agnostic part.

## Stack markers

`*.sln`, SDK-style `*.csproj` (`<Project Sdk="Microsoft.NET.Sdk.Web">`),
`Directory.Build.props`, `Directory.Packages.props` (central package management),
`global.json`. Variants that change the debt picture:
- **.NET Framework** (`packages.config`, `<TargetFrameworkVersion>v4.x`, `web.config`
  heavy): the runtime itself is the largest item; most modern analyzers do not run.
- **Multi-project vertical slices** (`*.MicroAPI`, `*.Managers`, `*.IServices`,
  `*.Entity`, `*.Dto`): complexity concentrates in `*Manager.cs` / `*Service.cs`;
  interfaces and DTO projects are near-zero complexity but big in line count.
- **Minimal APIs** (`app.MapPost(...)` lambdas in `Program.cs`): handlers are
  anonymous; `complexity.py` attributes them to the enclosing method, so read
  `Program.cs` by hand when it is long.

## Where the relevant code lives

- Business logic hotspots: `Managers/`, `Services/`, `Handlers/`, `BackgroundJobs/`,
  `*Importer.cs`, `*Calculator.cs`, `*Sync*.cs`. Start the manual trace from the top
  of `churn.md`, not from the folder structure.
- Suppressions: `GlobalSuppressions.cs`, `.editorconfig` (`dotnet_diagnostic.*.severity`),
  `<NoWarn>` and `<TreatWarningsAsErrors>` in csproj / `Directory.Build.props`.
- Runtime and package currency: `<TargetFramework(s)>`, `global.json`, `Dockerfile`
  `FROM mcr.microsoft.com/dotnet/aspnet:<v>`, `<PackageReference>` / `<PackageVersion>`.
- Excluded from metrics: `Migrations/`, `*.Designer.cs`, `*.g.cs`, `obj/`, `wwwroot/lib`.

## Dangerous / interesting APIs and patterns

Mirrored in `scripts/patterns/dotnet.json` (DEPR-* and MIX-* ids).
- **Obsolete APIs** (SYSLIB and CS0618 diagnostics): `WebClient`, `WebRequest`,
  `HttpWebRequest` (SYSLIB0014); `BinaryFormatter` (SYSLIB0011, removed in .NET 9 -
  security side owned by `audit-injection-vulnerabilities`); `RNGCryptoServiceProvider`,
  `SHA256Managed` (SYSLIB0021/0023); `Thread.Abort` (SYSLIB0006); `IHostingEnvironment`,
  `UseMvc`, `WebHost.CreateDefaultBuilder` (2.x hosting); EF Core `ExecuteSqlCommand`.
- **End-of-life markers**: `netcoreapp3.1`, `net5.0`, `net6.0`, `net7.0`; `net8.0` and
  `net9.0` both end 2026-11-10; `net4x` below 4.6.2; packages `IdentityServer4`
  (ended 2022-12-13), `System.Data.SqlClient`, `WindowsAzure.Storage`,
  `Microsoft.Azure.Storage.*`; EF Core majors follow the runtime.
- **Suppressions**: `#pragma warning disable` without a code (blanket) or without a
  matching `restore`; `[SuppressMessage]` without `Justification`; `<NoWarn>` lists
  that include `CS8600-CS8625` (nullable disabled piecemeal) or `CA2100`/`CA5xxx`
  (security); `.editorconfig` severity `none` on analyzer categories.
- **Inconsistent patterns**: Newtonsoft.Json beside System.Text.Json; EF Core beside
  Dapper beside raw `SqlCommand`; `ILogger<T>` beside static `Log.*` beside
  `Console.WriteLine`; AutoMapper beside Mapster beside hand mapping; FluentValidation
  beside DataAnnotations beside `if (string.IsNullOrWhiteSpace(model.X))` in controllers.
- **Complexity shapes**: `switch` on string codes repeated across managers; methods
  that validate, price, persist and notify in one body; `#region` blocks hiding
  500-line classes; `partial` classes spreading one god type over files.
- **Dead code**: types never referenced; private members flagged by IDE0051/IDE0052;
  parameters flagged by IDE0060; `.csproj` files not in the `.sln`.

## What "good" looks like

```xml
<PropertyGroup>
  <TargetFramework>net10.0</TargetFramework>
  <Nullable>enable</Nullable>
  <AnalysisLevel>latest-recommended</AnalysisLevel>
  <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
  <WarningsNotAsErrors>CS1591</WarningsNotAsErrors>
</PropertyGroup>
```

Suppressions are rare, scoped (`#pragma warning disable CA1822 // reason` ...
`restore`), and carry a justification. One JSON library, one data-access style per
bounded context, one logging abstraction. Methods on hot paths stay under CC 15 by
extracting steps (`ValidateRow`, `PriceLines`, `ApplyTax`) that each have tests.

## Manual trace checklist

1. Open the top hotspot. List the business rules its branches encode and whether any
   test pins them (`audit-test-coverage-and-ci` output). That list is the refactoring plan.
2. Confirm each dead-code candidate: search the solution and sibling repos for the type
   name and for string uses (`Type.GetType("...")`, Hangfire job names, DI scanning).
3. Check the upgrade path of every EOL item: `dotnet list package --outdated`, breaking
   changes per major, and whether the replacement is commercial (IdentityServer4 ->
   Duende licence) - that decides the effort size.
4. Read every suppression near authentication, SQL or crypto code; security ones become
   launch-risk candidates.
5. For each mixed-pattern family, find the boundary: is the mix per project (acceptable
   during a migration with an ADR) or inside one class (debt)?

## Stack-specific false positives

- Types found by reflection or assembly scanning: AutoMapper `Profile`, MediatR handlers,
  FluentValidation validators, `IEntityTypeConfiguration<T>`, Scrutor `.Scan(...)`,
  Hangfire jobs registered by type name - `dead_code.py` skips the common base types; others need a search.
- `<NoWarn>$(NoWarn);1591</NoWarn>` (missing XML docs) is benign noise.
- Duplicates in `Migrations/` and generated clients are excluded by default; if a repo keeps
  migrations elsewhere, pass `--exclude`.
- Expression-bodied members spanning several lines are not measured; they are rarely complex.

## Tooling

- Roslyn code metrics (cyclomatic complexity, maintainability index, class coupling): build
  `Metrics.exe` from dotnet/roslyn-analyzers or reference `Microsoft.CodeAnalysis.Metrics`
  **in a scratch copy** and run `dotnet build -t:Metrics`; rules CA1502 (complexity),
  CA1505 (maintainability), CA1506 (coupling) via `.editorconfig`.
- Currency: `dotnet list package --outdated --include-transitive`,
  `dotnet list package --deprecated`, `dotnet-outdated`, `upgrade-assistant analyze <sln>`.
- Dead code and style debt: `dotnet format analyzers --verify-no-changes --diagnostics IDE0051 IDE0052 IDE0060`.
- Broad debt dashboards: SonarQube / SonarCloud (`dotnet sonarscanner begin ...`), ReSharper
  `jb inspectcode`, NDepend (commercial). jscpd also tokenises C#.

## References

CWE-1121 (excessive McCabe complexity), CWE-1080 (oversized source file), CWE-561 (dead
code), CWE-1041 (redundant code), CWE-477 (obsolete function), CWE-1104 (unmaintained
third-party component), CWE-546 (suspicious comment). Obsolete API list:
https://learn.microsoft.com/dotnet/fundamentals/syslib-diagnostics/obsoletions-overview ;
support policy: https://dotnet.microsoft.com/platform/support/policy/dotnet-core ; code
metrics: https://learn.microsoft.com/visualstudio/code-quality/code-metrics-values
