# .NET / C# reference for audit-dependency-vulnerabilities

## Stack markers
`*.csproj`, `*.fsproj`, `*.sln`, `Directory.Packages.props` (central package
management), `Directory.Build.props`, `nuget.config`, `packages.lock.json`
(only if lock-file restore is on), legacy `packages.config`. Variants: SDK-style
projects (`<PackageReference>`) vs legacy `packages.config`; single solution
with many MicroAPI projects (every project has its own graph - scan the `.sln`
or each `.csproj`).

## Where the relevant code lives
- Direct dependencies: `<PackageReference Include="X" Version="1.2.3" />` in each `.csproj`;
  with CPM, versions live only in `Directory.Packages.props` (`<PackageVersion>`).
- Resolved graph (including transitives): `obj/project.assets.json` after restore.
- Feeds: `nuget.config` `<packageSources>`; a missing file means nuget.org only.
- Audit settings: `<NuGetAudit>`, `<NuGetAuditMode>`, `<NuGetAuditLevel>` in csproj/props.
- Container images: `Dockerfile` next to the host project (`FROM mcr.microsoft.com/dotnet/aspnet:8.0`).

## Dangerous / interesting APIs and patterns
- Widely known vulnerable packages to grep for in manifests: `Newtonsoft.Json` < 13.0.1
  (CVE-2024-21907 DoS), `System.Text.Json` < 8.0.4/8.0.5, `SharpZipLib` < 1.3.3,
  `BouncyCastle` < 2.2.1, `Microsoft.Data.SqlClient` < 5.1.3 (CVE-2024-0056),
  `System.Drawing.Common` on Linux (deprecated 6+), `MessagePack` < 2.5.108,
  `Azure.Identity` < 1.10.2, `Microsoft.IdentityModel.*` < 6.34/7.1.2 (CVE-2024-21319),
  `EPPlus` 4.x (LGPL and unmaintained), `RestSharp` < 106.11.8.
- Floating versions `Version="1.*"` or `Version="*"`; `<NuGetAudit>false</NuGetAudit>`;
  `<TreatWarningsAsErrors>` excluding NU19xx; HTTP feeds in `nuget.config`.
- Framework-provided packages: vulnerabilities in `Microsoft.AspNetCore.App` /
  `Microsoft.NETCore.App` are fixed by the runtime patch level, not by
  PackageReference. Check `global.json` / the base image tag.

## What "good" looks like
```xml
<PropertyGroup>
  <NuGetAudit>true</NuGetAudit>
  <NuGetAuditMode>all</NuGetAuditMode>            <!-- include transitives -->
  <NuGetAuditLevel>low</NuGetAuditLevel>
  <RestorePackagesWithLockFile>true</RestorePackagesWithLockFile>
</PropertyGroup>
<ItemGroup>
  <PackageReference Include="Newtonsoft.Json" Version="13.0.3" />
</ItemGroup>
```
CI step: `dotnet restore --locked-mode` then
`dotnet list Ibs.Inventory.sln package --vulnerable --include-transitive` and
fail when the output contains `has the following vulnerable packages`.

## Manual trace checklist
1. Every `Critical`/`High` row: find the consuming code (`grep -r "using Newtonsoft"`,
   `JsonConvert.DeserializeObject`) and decide whether attacker-controlled input
   reaches it (request bodies, uploaded files, webhook payloads).
2. Transitive rows: `dotnet nuget why <csproj> <PackageId>` names the direct parent;
   remediation is the parent bump or an explicit `<PackageReference>` for the fixed
   version (nearest-wins rule).
3. Runtime patch level: `FROM mcr.microsoft.com/dotnet/aspnet:8.0` floats to the
   latest patch at build time (fine); a pinned digest or `8.0.0` tag freezes old CVEs.
4. Shared projects (`SharedLibrary`, `SharedUtils.*`): one vulnerable reference there
   affects every service; report once with all project paths in Evidence.
5. `dotnet list package --outdated` for packages several majors behind - these are
   the ones that turn into breaking upgrades when a CVE lands.

## Stack-specific false positives
- `dotnet list package --vulnerable` reports the same transitive under every
  project and every target framework; de-duplicate on package@version.
- Analyzer/build-time packages (`Microsoft.CodeAnalysis.*`, `StyleCop.Analyzers`,
  `coverlet`) never ship to production; rate Low.
- `System.*` packages reported vulnerable but overridden by the shared framework at
  runtime (`FrameworkReference`) - confirm with `dotnet list package --include-transitive`
  which version is actually resolved.
- `Newtonsoft.Json` reported through `Microsoft.AspNetCore.Mvc.NewtonsoftJson`:
  fixed by bumping the ASP.NET package, not by pinning Newtonsoft alone.

## Tooling
- `dotnet list <sln|csproj> package --vulnerable --include-transitive --format json`
- `dotnet list <sln> package --outdated --include-transitive`
- `dotnet nuget why <csproj> <PackageId>` (SDK 8.0.400+)
- `dotnet restore --locked-mode` (with packages.lock.json)
- `trivy fs --scanners vuln .` also reads `packages.lock.json` / `*.deps.json`
- `trivy image mcr.microsoft.com/dotnet/aspnet:8.0` for the base image

## References
CWE-1395 (dependency on vulnerable third-party component), CWE-1104 (unmaintained
component), OWASP A06:2021, ASVS 14.2.1-14.2.6, NuGet audit docs
(learn.microsoft.com/nuget/concepts/auditing-packages), GitHub Advisory Database
(github.com/advisories?ecosystem=nuget).
