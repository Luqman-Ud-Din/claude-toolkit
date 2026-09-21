# .NET / ASP.NET Core reference for audit-security-headers-and-middleware

## Stack markers
`*.csproj` with `Microsoft.NET.Sdk.Web`, `Program.cs` (minimal hosting) or `Startup.cs` (`Configure(IApplicationBuilder app, ...)`), `appsettings*.json`, `web.config` (IIS: `<httpProtocol><customHeaders>`, `<requestLimits maxAllowedContentLength>`), Ocelot (`ocelot*.json`) / YARP (`ReverseProxy` section) gateways - the gateway's pipeline is the one the browser sees for headers and CORS.

## Where the relevant code lives
`Program.cs` / `Startup.cs` (every `app.Use*`/`app.Map*` in order; `builder.Services.AddCors/AddAuthentication/AddRateLimiter/AddAntiforgery`), `Extensions/*ServiceCollectionExtensions.cs` and `*ApplicationBuilderExtensions.cs` (pipeline pieces hidden behind `app.UseCustomMiddleware()` - open them), `Middleware/*.cs` (custom header/exception middleware), `appsettings*.json` (`Kestrel:Limits:MaxRequestBodySize`, `AllowedHosts`, `Cors:Origins`, `IpRateLimiting`), controllers setting cookies (`Response.Cookies.Append`), `Properties/launchSettings.json` (dev only), `web.config`, `nginx.conf`/`Dockerfile` for reverse proxies (`UseForwardedHeaders` needed for correct scheme/IP).

## Dangerous / interesting APIs and patterns
- Headers: absence of any header middleware; `app.Use(async (ctx, next) => { ctx.Response.Headers.Append("X-Frame-Options", ...)` (custom - check the set), `NWebsec.AspNetCore.Middleware` (`UseCsp`, `UseXfo`, `UseHsts`), `Microsoft.AspNetCore.HeaderPropagation` (not security), `app.UseHsts()` with `AddHsts(o => o.MaxAge = TimeSpan.FromDays(1))` (too short), `UseHsts` skipped in prod because it sits inside `if (!env.IsDevelopment())` inverted; `AddServerHeader = false` on Kestrel (`ConfigureKestrel(o => o.AddServerHeader = false)`) missing -> `Server: Kestrel`; `X-Powered-By` from IIS (`web.config` `<remove name="X-Powered-By" />`).
- Order: `app.MapControllers()`/`UseEndpoints` before `UseAuthentication`/`UseAuthorization`; `UseAuthorization` before `UseAuthentication`; `UseCors` after `UseAuthentication` (preflights 401) or after `UseRouting` missing (older versions); `UseExceptionHandler` not first; `UseDeveloperExceptionPage` outside `IsDevelopment()`; `UseHttpsRedirection` after endpoints; `UseRateLimiter` before `UseRouting` (endpoint policies ignored) - place after routing.
- CORS: `AllowAnyOrigin()`, `SetIsOriginAllowed(_ => true)` with `AllowCredentials()`, `WithOrigins("*")`, `AllowAnyHeader().AllowAnyMethod()` with credentials, origins from config that includes `http://localhost` in production, `[EnableCors]` with a permissive named policy, Ocelot global CORS.
- Cookies: `Response.Cookies.Append(name, value)` with no `CookieOptions` (HttpOnly **false** by default for `Append`; `Secure` false), `HttpOnly = false`, missing `SameSite`, `SameSite = SameSiteMode.None` without `Secure = true`, `CookiePolicyOptions { MinimumSameSitePolicy = SameSiteMode.None }`, `AddCookie(o => o.Cookie.HttpOnly = false)`, `Cookie.SecurePolicy = CookieSecurePolicy.SameAsRequest` behind a proxy without forwarded headers (cookie ends up non-Secure), session cookie `AddSession(o => o.Cookie.HttpOnly = false)`.
- CSRF: cookie auth (`AddCookie`, `AddIdentity`, `AddSession` carrying auth) with controllers lacking `[ValidateAntiForgeryToken]`/`[AutoValidateAntiforgeryToken]` and no `UseAntiforgery()`; `[IgnoreAntiforgeryToken]` on POST actions; minimal APIs with cookie auth and no `AddAntiforgery` (.NET 8+); Razor forms without `asp-antiforgery`.
- Rate limiting: no `AddRateLimiter`/`UseRateLimiter` and no `AspNetCoreRateLimit` (`UseIpRateLimiting`, `IpRateLimiting` in appsettings); `[EnableRateLimiting]` missing on login/OTP/register/forgot-password actions; `[DisableRateLimiting]` on sensitive actions; limiter keyed on `X-Forwarded-For` without `UseForwardedHeaders` + `KnownProxies`.
- Body limits: `MaxRequestBodySize = null` or `long.MaxValue`; `[DisableRequestSizeLimit]`; `[RequestSizeLimit(int.MaxValue)]`; `FormOptions.MultipartBodyLengthLimit = long.MaxValue`; `web.config` `maxAllowedContentLength="4294967295"`.
- Errors: `UseDeveloperExceptionPage()` unconditional; `app.UseExceptionHandler` absent and controllers returning `ex.ToString()`; `ProblemDetails` with `Detail = ex.StackTrace`.

## What "good" looks like
```csharp
var app = builder.Build();
app.UseExceptionHandler("/error");                               // 1 exception
if (!app.Environment.IsDevelopment()) app.UseHsts();             // 2 hsts (AddHsts: MaxAge 365d, IncludeSubDomains, Preload)
app.UseHttpsRedirection();                                       // 3 https
app.Use(async (ctx, next) => {                                   // headers (or NWebsec)
    var h = ctx.Response.Headers;
    h["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'";
    h["X-Content-Type-Options"] = "nosniff"; h["X-Frame-Options"] = "DENY";
    h["Referrer-Policy"] = "strict-origin-when-cross-origin";
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()";
    await next();
});
app.UseStaticFiles();                                            // 4 static
app.UseRouting();                                                // 5 routing
app.UseCors("Frontend");                                         // 6 cors: WithOrigins(cfg["Cors:Origins"]).AllowCredentials() only if cookies
app.UseAuthentication();                                         // 7 authn
app.UseAuthorization();                                          // 8 authz
app.UseRateLimiter();                                            // 9 ratelimit (AddRateLimiter: "login" fixed window 5/min by IP+user)
app.MapControllers();                                            // 10 endpoints
// Kestrel: builder.WebHost.ConfigureKestrel(o => { o.AddServerHeader = false; o.Limits.MaxRequestBodySize = 10 * 1024 * 1024; });
// Cookies: new CookieOptions { HttpOnly = true, Secure = true, SameSite = SameSiteMode.Strict, Path = "/api/auth/refresh" }
```

## Manual trace checklist
1. Pipeline file(s) for every host in the solution (gateway first): confirm the extractor's order, expand `app.UseXyz()` extension methods.
2. Headers: which middleware emits them in production; run the live check if a URL exists; on IIS also read `web.config`.
3. Auth model: `AddJwtBearer` only (bearer) vs `AddCookie`/`AddIdentity`/`AddSession` - decide CSRF requirement; check Razor/MVC forms.
4. Every `Response.Cookies.Append` and every `Cookie.*` option in `AddCookie`/`AddSession`/`AddAntiforgery`.
5. CORS policy definitions and which one `UseCors` applies; compare origins with the frontend's production host.
6. Rate limiting on `AuthController` login/OTP/forgot-password; `ForwardedHeaders` configured if behind nginx/ingress.
7. Kestrel/IIS body limits; `[RequestSizeLimit]`/`[DisableRequestSizeLimit]` on upload actions.
8. Ocelot: `GlobalConfiguration` and per-route `AuthenticationOptions`; gateway is where headers must be added if services are internal.

## Stack-specific false positives
- `UseRateLimiter` after `UseAuthorization` is the documented placement - not out of order.
- `UseCors` between `UseRouting` and `UseAuthentication` is correct even though it precedes auth.
- `AllowAnyOrigin()` on a bearer-only public API without credentials - Low/Info, not High.
- `Response.Cookies.Append` for a non-auth preference cookie without HttpOnly - Low.
- `UseDeveloperExceptionPage()` inside `if (app.Environment.IsDevelopment())`.
- Missing `UseHttpsRedirection` when TLS terminates at the ingress and `UseForwardedHeaders` is configured - note, not a finding.

## Tooling
- `python scripts/extract_middleware.py <repo> --stack dotnet` (bundled).
- `python scripts/check_headers.py https://host` (bundled) when a URL is supplied.
- `dotnet list package` for `NWebsec.AspNetCore.Middleware` / `AspNetCoreRateLimit` presence.
- `SecurityCodeScan` SCS0016 (CSRF), SCS0008/SCS0009 (cookie flags).

## References
Microsoft docs "ASP.NET Core Middleware" (order diagram), "Enforce HTTPS", "Rate limiting middleware", "Prevent CSRF", "SameSite cookies"; OWASP HTTP Headers and CSRF cheat sheets. CWE-306, CWE-1004, CWE-614, CWE-352, CWE-942, CWE-307, CWE-400, CWE-693; ASVS 1.4.4, 3.4.x, 4.2.2, 13.2.x, 14.4.x, 14.5.x; OWASP A01/A05/A07:2021.
