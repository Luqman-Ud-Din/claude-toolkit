# .NET / ASP.NET Core reference for audit-secrets-and-config

## Stack markers
`*.csproj`, `appsettings*.json`, `Program.cs`/`Startup.cs`, `web.config`.

## Where the relevant code lives
`appsettings.json` + `appsettings.{Environment}.json` (config values), `Program.cs`/`Startup.cs` (CORS, HTTPS/HSTS, dev exception page, env checks), `launchSettings.json` (env vars, not shipped), `*.csproj`/`Dockerfile` (`ASPNETCORE_ENVIRONMENT`), user-secrets (`<UserSecretsId>` in the csproj - dev only).

## Dangerous / interesting keys and patterns
- Secrets in config: `ConnectionStrings:*` with `Password=`, `Jwt:Key`/`SigningKey`, `*:ApiKey`/`ClientSecret`, `sk_live_...`. These must not be literals in a committed file - `dotnet user-secrets` in dev, env vars / Key Vault in prod.
- Debug in prod: `"DetailedErrors": true`, `LogLevel: Debug/Trace` in `appsettings.Production.json`, `app.UseDeveloperExceptionPage()` not guarded by `if (env.IsDevelopment())`.
- Environment flag: confirm `ASPNETCORE_ENVIRONMENT=Production` in the deploy; a missing/Development value keeps dev behavior on.
- HTTPS/HSTS: `app.UseHttpsRedirection()` and `app.UseHsts()` present for prod.
- CORS: `AllowAnyOrigin()` or `SetIsOriginAllowed(_ => true)` combined with `AllowCredentials()` is the classic dangerous (and, for AllowAnyOrigin, invalid) combination - a reflected-origin + credentials lets any site make authenticated calls.

## What "good" looks like
```csharp
var cs = builder.Configuration.GetConnectionString("Default");   // value from env/Key Vault
builder.Configuration.AddAzureKeyVault(...);                     // or AddUserSecrets in dev
app.UseHsts(); app.UseHttpsRedirection();
if (env.IsDevelopment()) app.UseDeveloperExceptionPage(); else app.UseExceptionHandler("/error");
services.AddCors(o => o.AddPolicy("app", p =>
    p.WithOrigins("https://app.example.com").AllowAnyHeader().AllowCredentials()));
```

## Manual trace checklist
1. Open every `appsettings*.json` - any literal secret? Is the same key overridden by env in prod?
2. Confirm the production config disables detailed errors and debug logging.
3. Confirm the dev exception page is behind `IsDevelopment()`.
4. Read the CORS policy - wildcard/reflected origin + credentials?
5. Run `git_secret_scan.py` for secrets already committed to history.

## Stack-specific false positives
Empty/placeholder values in the base `appsettings.json` overridden by env in prod; `*.example`/template files; a wildcard-origin CORS WITHOUT credentials on a public read-only API (still note it, lower severity).

## Tooling
`dotnet user-secrets`, `Microsoft.CodeAnalysis.NetAnalyzers`, plus the cross-stack scanners in `references/tool-candidates.md`. Scripts: `git_secret_scan.py`, `config_key_inventory.py`.

## References
CWE-798 (hard-coded credentials), CWE-321 (hard-coded crypto key), CWE-489 (active debug code), CWE-942 (permissive CORS), CWE-16 (config). ASVS 2.10, 14.1, 14.4/14.5. OWASP A05:2021 (misconfig), A02:2021 (crypto/secrets).
