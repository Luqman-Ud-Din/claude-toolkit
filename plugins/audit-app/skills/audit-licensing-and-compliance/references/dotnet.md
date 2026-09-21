# .NET / C# reference for audit-licensing-and-compliance

Where licence information lives for NuGet dependencies, what the automated pass can and
cannot resolve offline, which well-known packages have surprising terms, and how the
notices file is normally shipped in a .NET product.

## Stack markers
`*.sln`, `*.csproj` / `*.fsproj` with `<PackageReference>`, `Directory.Packages.props`
(central package management - versions live there, not in the csproj), `packages.lock.json`
(when `RestorePackagesWithLockFile` is on), `nuget.config` (private feeds). Legacy:
`packages.config`.

## Where the relevant code lives
- Direct dependencies: `<PackageReference Include="X" Version="1.2.3" />` in each csproj; `Directory.Packages.props` `<PackageVersion>` when central management is used (the script reads both because it walks `.props`).
- Resolved graph: `obj/project.assets.json` per project (transitive list; ignored by the script because `obj/` is skipped - use `dotnet-project-licenses --include-transitive`).
- Licence metadata: `~/.nuget/packages/<id>/<ver>/<id>.nuspec` -> `<license type="expression">MIT</license>` (SPDX) or `<license type="file">LICENSE.txt</license>` (read the file next to it) or legacy `<licenseUrl>`.
- Non-NuGet binaries: `<Reference Include="Vendor.Lib"><HintPath>..\libs\Vendor.Lib.dll</HintPath></Reference>` - no metadata at all.
- Private feeds in `nuget.config`: packages from a company feed may be internal (fine) or re-hosted third-party (still need a licence).
- Shipping the notices: `THIRD-PARTY-NOTICES.txt` at the solution root copied via `<None Include="..." CopyToOutputDirectory="PreserveNewest" />`, or embedded in the About page / Swagger description.

## Dangerous / interesting APIs and patterns
- `PackageReference` to **iText7 / iTextSharp** (AGPL or commercial), **Ghostscript.NET** (AGPL wrapper around GPL Ghostscript), **MySql.Data** (GPL-2.0 with FOSS exception - proprietary use needs Oracle's commercial licence; `MySqlConnector` is MIT), **QuestPDF** (Community licence has revenue caps), **FluentAssertions 8+** (Xceed commercial for non-OSS), **SharpZipLib** (MIT since 1.x; older 0.86 is GPL with exception), **EPPlus 5+** (Polyform Noncommercial; 4.5.3.3 is LGPL), **Syncfusion / Telerik / DevExpress** (commercial per-developer).
- `<PackageLicenseExpression>` in the project's *own* csproj declaring something the company did not intend.
- `HintPath` DLLs and `*.dll` checked into the repo.
- Fonts embedded for PDF/report generation (`*.ttf` in `Resources/`) - the font licence, not the PDF library's, governs redistribution.
- Docker `FROM mcr.microsoft.com/dotnet/aspnet` is MIT-licensed tooling on a Debian base (fine); custom base images need `docker inspect`.

## What "good" looks like
```xml
<!-- Directory.Build.props -->
<ItemGroup>
  <None Include="$(MSBuildThisFileDirectory)THIRD-PARTY-NOTICES.md" CopyToOutputDirectory="PreserveNewest" Link="THIRD-PARTY-NOTICES.md" />
</ItemGroup>
```
```bash
# CI gate
dotnet-project-licenses -i Ibs.Inventory.sln --include-transitive -j --outfile licenses.json \
  --allowed-license-types MIT Apache-2.0 BSD-3-Clause BSD-2-Clause ISC MS-PL
```
A package with `review` verdict gets a one-line decision in the notices file.

## Manual trace checklist
1. Open every `unknown` NuGet package: is it in a private feed (internal code) or a public package missing from the cache (`dotnet restore` then re-run)?
2. For each `HintPath` DLL: find the vendor and licence; note whether it is redistributable.
3. EPPlus / iText / QuestPDF / MySql.Data present? Confirm the version's licence (they changed between majors) and whether a commercial licence key is configured (`ExcelPackage.LicenseContext`, `QuestPDF.Settings.License`).
4. Fonts under `Resources/` or embedded as resources: licence file present?
5. Where is the notices file shipped - output directory, container image, About page? If nowhere, the attribution finding stands.

## Stack-specific false positives
- `Microsoft.*` and `System.*` packages: MIT; `unknown` only because the cache was empty.
- `<PackageReference>` with `PrivateAssets="all"` (analyzers, build-time tools) - not shipped; downgrade to Info.
- Test projects' packages (xunit, Moq, FluentAssertions) - not shipped; list under dev scope.
- `EPPlus` 4.5.x is LGPL (review), not Polyform.

## Tooling
- `dotnet-project-licenses` (global tool) - full tree with licence types, JSON/Markdown output.
- `dotnet CycloneDX <sln> -o sbom/` - SBOM with licence ids.
- `dotnet list package --include-transitive` - graph without licences (pair with nuspec reads).
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py --patterns scripts/patterns/dotnet.json` - vendored GPL headers, copyleft `PackageLicenseExpression`, HintPath DLLs, known-copyleft packages, base images.

## References
NuGet docs "Package licensing" (`license` element, SPDX expressions); dotnet-project-licenses README;
SPDX licence list; ASVS 4.0.3 V14.2 (dependency management); CWE-1104 (unmaintained third-party components; used here as the closest id for unvetted components).
