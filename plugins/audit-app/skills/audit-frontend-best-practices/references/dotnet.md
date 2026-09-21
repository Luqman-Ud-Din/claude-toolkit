# .NET / C# reference for audit-frontend-best-practices

This skill audits frontend code. When the repo also contains an ASP.NET Core
backend, the backend owns a small part of "frontend best practice": how the
SPA's static files are served. Check only the items below here; everything
else about the backend belongs to sibling skills (listed at the end).

## Stack markers

`*.csproj`, `*.sln`, `Program.cs`. Frontend-serving variants: `Microsoft.AspNetCore.SpaServices.Extensions`
(`UseSpa`, `UseSpaStaticFiles`), plain `UseStaticFiles` over a copied `dist/`, a Razor host page,
or the SPA is served by a separate web server / CDN (then nothing here applies - say so).

## Where the relevant code lives

`Program.cs` / `Startup.cs` middleware pipeline; `appsettings*.json` (`ResponseCompression`,
`StaticFiles`); `web.config` (IIS: `<staticContent>`, `<urlCompression>`, `<httpCompression>`);
`*.csproj` `<SpaRoot>`, `<SpaProxyServerUrl>`, `PublishRunWebpack`/`ng build` targets;
Ocelot / YARP gateway config if the SPA is behind a gateway (`ocelotconfig.json`, `yarp` section).

## Dangerous / interesting APIs and patterns (this skill's slice only)

- `app.UseStaticFiles()` with no `OnPrepareResponse` and no `Cache-Control` for hashed assets;
  or `Cache-Control: no-cache` applied to everything including `*.[hash].js`.
- `index.html` served with a long `max-age` (users stuck on old bundles after a deploy).
- No `UseResponseCompression()` / `AddResponseCompression(o => o.EnableForHttps = true)` and
  no compression at the reverse proxy: JS/CSS shipped uncompressed. Confirm at the proxy
  (nginx `gzip on`, IIS `<httpCompression>`) before rating.
- `MapFallbackToFile("index.html")` missing: deep links 404 on refresh (SPA routing broken).
- `.map` files present in the published `wwwroot` (`<Content Include="**/*.map">` or a copy
  task that does not exclude them) - source maps shipped even if the frontend config is right.
- `UseSpa(spa => spa.UseAngularCliServer(...))` / `UseProxyToSpaDevelopmentServer` reachable in
  a non-Development branch (dev server started in production).
- `csproj` build target running `npm run build` without `--configuration production`.

## What "good" looks like

```csharp
builder.Services.AddResponseCompression(o => { o.EnableForHttps = true; o.Providers.Add<BrotliCompressionProvider>(); });
app.UseResponseCompression();
app.UseStaticFiles(new StaticFileOptions {
    OnPrepareResponse = ctx => {
        var h = ctx.Context.Response.Headers;
        h.CacheControl = ctx.File.Name.Contains('.') && Regex.IsMatch(ctx.File.Name, @"\.[0-9a-f]{8,}\.")
            ? "public,max-age=31536000,immutable" : "no-cache";
    }});
app.MapFallbackToFile("index.html");
```
```xml
<Target Name="PublishSpa" AfterTargets="ComputeFilesToPublish">
  <Exec WorkingDirectory="$(SpaRoot)" Command="npm run build -- --configuration production" />
  <ItemGroup><DistFiles Include="$(SpaRoot)dist\**" Exclude="$(SpaRoot)dist\**\*.map" /></ItemGroup>
</Target>
```

## Manual trace checklist

1. Is the SPA served by this backend at all? Read `Program.cs` for `UseStaticFiles`/`UseSpa`/
   `MapFallbackToFile`. If not, record "backend does not serve frontend" under checked scope
   and stop.
2. Compression: middleware or proxy? Evidence: a `curl -I --compressed https://host/main.js`
   showing `content-encoding: br|gzip` closes the item.
3. Cache headers on `index.html` vs hashed chunks.
4. Publish pipeline: which frontend build command and configuration; are `.map` files excluded.

## Stack-specific false positives

- Compression disabled in Kestrel but enabled at nginx/IIS/CDN: fine; name the layer.
- `Cache-Control: no-cache` on `index.html` is correct, not a finding.
- `UseSpa` dev-server branch guarded by `if (app.Environment.IsDevelopment())`: fine.

## Tooling

`dotnet publish -c Release` then inspect `wwwroot/` for `*.map`; `curl -I --compressed`
against the deployed host; `dotnet list package` to confirm `SpaServices.Extensions` version.

## Deferred to sibling skills

Security headers, CSP and HSTS: `audit-security-headers-and-middleware`. API performance,
caching and N+1: `audit-performance-and-scalability`. Gateway routing correctness:
`audit-api-contract`. Everything else about the backend is out of scope for this skill.

## References

ASP.NET Core static files: https://learn.microsoft.com/aspnet/core/fundamentals/static-files;
response compression: https://learn.microsoft.com/aspnet/core/performance/response-compression;
CWE-540 (source maps), CWE-525 (cache of sensitive pages), ASVS-14.3.2.
