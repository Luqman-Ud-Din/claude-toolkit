# .NET / C# reference for audit-injection-vulnerabilities

## Stack markers
`*.csproj`, `*.sln`, `Program.cs`, `appsettings*.json`. Variants: EF Core vs Dapper vs raw `SqlCommand`; controllers vs minimal APIs; gateway (Ocelot/YARP) in front means the downstream services may trust headers the gateway forwards.

## Where the relevant code lives
`*Manager.cs` / `*Repository.cs` / `*Service.cs` (query building), `Controllers/**` (sources: `[FromQuery]`, `[FromBody]`, `[FromRoute]`, `IFormFile.FileName`, `HttpContext.Request.Headers`), `BackgroundJobs/**` (Hangfire args come from whoever enqueued), `*DbContext.cs` (`ExecuteSqlRaw` in seeders/migrations), report/export builders (EPPlus, PDF), file/image handlers, integration clients (Shopify, Google Drive, FBR, SMS).

## Dangerous / interesting APIs and patterns
- SQL: `FromSqlRaw(`, `ExecuteSqlRaw(`, `ExecuteSqlRawAsync(`, `SqlQueryRaw<`, `new SqlCommand(` / `NpgsqlCommand` / `MySqlCommand` with `CommandType.Text` and a non-literal text, `SqlDataAdapter(` with a string, Dapper `Query(`/`Execute(` with `$"..."` or `+`, `string.Format(`/`$"` producing `SELECT|INSERT|UPDATE|DELETE|EXEC`, `EXEC(@sql)` / `sp_executesql` with concatenated text, dynamic `ORDER BY` from `sortColumn`/`SortDir`, `DbFunctions` misuse. `EF.Functions.Like(col, pattern)` is parameterized but `%`/`_` in `pattern` change semantics (not injection).
- NoSQL: MongoDB driver `BsonDocument.Parse(userString)`, `Builders<T>.Filter.Where` with `$where`, `FilterDefinition` built from raw JSON, Cosmos `new QueryDefinition("... " + x)`.
- CMD: `Process.Start(` with `"cmd"`/`"/bin/sh"`/`"bash"`/`"powershell"` and `-c`/`/c`, `ProcessStartInfo { FileName = ..., Arguments = ... + x }`, `UseShellExecute = true` with a user path.
- PATH: `Path.Combine(root, userValue)` (an absolute or `..` second argument replaces the root), `File.ReadAllText|ReadAllBytes|WriteAllBytes|Delete|Exists|OpenRead(`, `Directory.GetFiles(`, `PhysicalFile(`, `File(...)` result, `new FileStream(`, `IFormFile.FileName` used in a path, `Server.MapPath`, `IWebHostEnvironment.WebRootPath + `.
- LDAP: `new DirectorySearcher(` with `Filter = "(&(uid=" + x`, `DirectoryEntry(path + x)`, `System.DirectoryServices.Protocols.SearchRequest(`.
- XPATH: `SelectNodes(`, `SelectSingleNode(`, `XPathExpression.Compile(`, `XPathNavigator.Evaluate(` with concatenation; also `XmlDocument.XmlResolver` non-null + DTD (XXE, report under this class with CWE-611).
- TMPL: `RazorEngine.Razor.Parse(`, `Engine.Razor.RunCompile(userTemplate`, `Scriban.Template.Parse(x`, `Handlebars.Compile(x` where `x` is user text, `String.Format(userFormat, ...)` (format-string injection).
- SSRF: `new HttpClient().GetAsync(url)`, `_httpClient.GetStringAsync(model.Url)`, `HttpClientFactory.CreateClient().SendAsync(new HttpRequestMessage(..., userUrl))`, `WebClient.DownloadString(`, `WebRequest.Create(`, `new Uri(userString)` reaching a client; also image-by-URL, webhook, "import from URL", and OAuth callback fetchers.
- DESER: `BinaryFormatter`, `SoapFormatter`, `NetDataContractSerializer`, `LosFormatter`, `ObjectStateFormatter`, `JavaScriptSerializer` with `SimpleTypeResolver`, Newtonsoft `TypeNameHandling.All|Auto|Objects|Arrays`, `JsonSerializerSettings { TypeNameHandling = ...}`, `XmlSerializer(Type.GetType(userString))`, `DataContractSerializer` with `DataContractResolver` that accepts any type.

## What "good" looks like
```csharp
// SQL - value is sent as a parameter, sort column is allow-listed
var sort = AllowedSort.TryGetValue(model.SortColumn ?? "", out var col) ? col : "CreatedOn";
var rows = await _ctx.Sales
    .FromSqlInterpolated($"SELECT * FROM Sales WHERE BranchId = {branchId} AND CompanyId = {companyId}")
    .OrderBy(EF.Property<object>(s => s, sort)).ToListAsync(ct);
// FromSqlRaw("... = {0}", value) is equally safe: {0} becomes @p0.

// PATH - name stripped, resolved, prefix-checked
var safeName = Path.GetFileName(fileName);
var full = Path.GetFullPath(Path.Combine(_root, safeName));
if (!full.StartsWith(_root + Path.DirectorySeparatorChar, StringComparison.Ordinal)) return NotFound();

// CMD - no shell, argument list
var psi = new ProcessStartInfo("convert") { UseShellExecute = false };
psi.ArgumentList.Add(full); psi.ArgumentList.Add(outPath);

// SSRF - parse, restrict scheme, allow-list host
if (!Uri.TryCreate(model.Url, UriKind.Absolute, out var uri) || uri.Scheme != "https" || !AllowedHosts.Contains(uri.Host)) return BadRequest();

// DESER - System.Text.Json with no polymorphism, or Newtonsoft TypeNameHandling.None + a SerializationBinder allow-list.
```

## Manual trace checklist
1. Every `GetPaginationList` / DataTable-style endpoint: how `SortColumn`, `SortDirection`, `SearchTerm`, and custom-field filters reach the query. Dynamic ordering by string is the most common .NET SQLi shape.
2. Report and export managers (`*ReportManager`, EPPlus builders): look for hand-written SQL for performance.
3. File upload/download: `IFormFile.FileName`, "download by name" endpoints, image resize paths (`SixLabors` load from a path), Google Drive sync paths.
4. Integration clients: any endpoint that accepts a URL (webhooks, logo/image URL, "import from Shopify store domain").
5. Hangfire / background jobs: arguments are strings stored in the job store; whoever can enqueue controls them.
6. `TypeNameHandling` anywhere in `JsonSerializerSettings`, especially global `AddNewtonsoftJson(o => ...)`.
7. Custom `DbCommandInterceptor` or "multi-tenant" code that swaps database names into connection strings or `USE [db]` statements built from a claim - a claim is user-influenced if the token issuer trusts a registration form.

## Stack-specific false positives
- `FromSqlRaw("... {0}", arg)` and `FromSqlInterpolated($"...")` are parameterized. `FromSqlRaw($"...")` (interpolated string passed to *Raw*) is **not**.
- `ExecuteSqlRaw` in `OnModelCreating`/seed code with literal SQL.
- `Path.Combine(root, "fixed.txt")` and `Path.Combine(root, Guid.NewGuid() + ext)`.
- `Process.Start("https://...")` used to open a browser in desktop tools.
- `HttpClient` calls with a base address from configuration and only path/query from input: not SSRF, but check for path traversal in the URL (`../admin`).
- `JsonConvert.DeserializeObject<T>(x)` with default settings (`TypeNameHandling.None`) is safe.

## Tooling
- `dotnet add package SecurityCodeScan.VS2019` then `dotnet build` (rules SCS0002 SQL, SCS0001 command, SCS0018 path, SCS0028 deserialization); or `Microsoft.CodeAnalysis.NetAnalyzers` CA2100, CA3001-CA3012, CA2300-CA2330.
- `semgrep --config p/csharp <repo>` if semgrep is installed.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/dotnet.json` (bundled).

## References
OWASP Query Parameterization and SQL Injection Prevention cheat sheets; OWASP SSRF Prevention; Microsoft "BinaryFormatter security guide"; EF Core "Raw SQL queries" docs (FromSqlRaw vs FromSqlInterpolated). CWE-89, 78, 22, 90, 643, 918, 502, 1336; ASVS 5.3.x, 5.5.x, 12.3.x, 12.6.1; OWASP A03:2021, A08:2021, A10:2021.
