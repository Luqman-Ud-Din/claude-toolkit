# .NET / C# reference for audit-client-auth-and-storage

Client auth is a frontend topic; this file covers what the ASP.NET Core side
contributes to the flow the client implements - how tokens are issued, how
long they live, whether refresh and logout exist server-side, and whether the
API lets the client choose the safer cookie model. Everything about validating
tokens and enforcing roles belongs to `audit-authz-and-access-control`; cookie
flags, CORS and headers belong to `audit-security-headers-and-middleware`.

## Stack markers
`*.csproj` with `Microsoft.AspNetCore.Authentication.JwtBearer`, `Microsoft.AspNetCore.Identity`, `Duende.IdentityServer`/`OpenIddict`; `appsettings*.json` `Jwt:*` / `Authentication:*` sections; Ocelot/YARP gateway config.

## Where the relevant code lives
`Program.cs`/`Startup.cs` (`AddAuthentication().AddJwtBearer(...)`, `AddCookie(...)`, `AddCors`), `Controllers/Auth*Controller.cs`/`Account*Controller.cs`/`Login*` (token issuance, refresh, logout endpoints), `*TokenService.cs`/`JwtHelper.cs` (`JwtSecurityTokenHandler`, `SecurityTokenDescriptor`, expiry), refresh-token entity and repository (`RefreshToken`, `UserToken`), `appsettings*.json` (`Jwt:ExpiryMinutes`, `Jwt:Key`), gateway `ocelotconfig.json` (`AuthenticationOptions`, which routes are anonymous), SignalR/WebSocket hubs (`access_token` query string).

## What this skill checks on the server side
- **Issuance shape**: does login return the JWT in the JSON body (forces the SPA to store it) or set an HttpOnly cookie (`Response.Cookies.Append("access_token", token, new CookieOptions { HttpOnly = true, Secure = true, SameSite = SameSiteMode.Lax })`)? Both can be fine; the client finding cites which.
- **Lifetimes**: `expires: DateTime.UtcNow.AddDays(30)` on an access token is a server contribution to the client's storage risk (a stolen token stays valid for 30 days). Look for `Expires`, `AddMinutes`, `AddHours`, `AddDays`, `TokenValidationParameters.ClockSkew`, `RequireExpirationTime = false`, `ValidateLifetime = false`.
- **Refresh**: a `POST /auth/refresh` endpoint exists; refresh tokens are random (`RandomNumberGenerator.GetBytes(64)`), stored hashed, single-use/rotated, bound to the user and revocable; refresh accepted from the body (client stores it - see client STORE rules) or from an HttpOnly cookie (preferred).
- **Logout / revocation**: `POST /auth/logout` deletes the refresh token row and clears the cookie; without it the client's "logout" is cosmetic for the refresh token's lifetime. JWT denylist or short access-token TTL.
- **Where the token is read**: `JwtBearerEvents.OnMessageReceived` reading `context.Request.Query["access_token"]` (SignalR) or cookies - tells you what the client may legitimately do.
- **Public identifiers vs secrets**: any value the API hands to the client (`/config` endpoints returning keys, `appsettings` values exposed through a `ClientSettings` DTO) - check they are public identifiers only.
- **CORS**: `AllowAnyOrigin()` with `AllowCredentials()` (invalid combination, or `SetIsOriginAllowed(_ => true)` with credentials) makes cookie auth exploitable cross-site - report under the headers skill, cite it here if the client relies on cookies.

## What "good" looks like
```csharp
// Program.cs
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer(o => {
    o.TokenValidationParameters = new() { ValidateLifetime = true, ClockSkew = TimeSpan.FromSeconds(30), /* issuer, audience, key */ };
    o.Events = new JwtBearerEvents { OnMessageReceived = ctx => { ctx.Token ??= ctx.Request.Cookies["access_token"]; return Task.CompletedTask; } };
});
// AuthController
var access = _tokens.CreateAccessToken(user, TimeSpan.FromMinutes(15));
var refresh = _tokens.CreateRefreshToken(user);                     // random, hashed in DB, rotated on use
Response.Cookies.Append("refresh_token", refresh, new CookieOptions { HttpOnly = true, Secure = true, SameSite = SameSiteMode.Strict, Path = "/api/auth/refresh", Expires = DateTimeOffset.UtcNow.AddDays(14) });
return Ok(new { accessToken = access, expiresIn = 900 });          // access token in body for memory storage, or as HttpOnly cookie too
[HttpPost("logout")] public async Task<IActionResult> Logout() { await _tokens.RevokeAsync(User); Response.Cookies.Delete("refresh_token"); return NoContent(); }
```

## Manual trace checklist
1. Login endpoint: response DTO fields (`Token`, `RefreshToken`, `ExpiresAt`) and cookie usage.
2. Token factory: access TTL, refresh TTL, `ValidateLifetime`.
3. Refresh endpoint: rotation, reuse detection, where the refresh token is read from.
4. Logout endpoint: exists? revokes? clears cookies?
5. `/config`/`/settings` endpoints returning keys to the client.
6. SignalR hubs: `access_token` in query string (acceptable for WebSockets only; make sure it is not logged).

## Stack-specific false positives
- Access token in the JSON body is acceptable when the client keeps it in memory and uses an HttpOnly refresh cookie.
- `ClockSkew` up to 5 minutes (the default) is not a finding.
- `AllowAnyOrigin()` without credentials on a bearer-only API is a headers-skill topic, not a client-auth finding.

## Tooling
- `grep -rn "AddDays\|AddHours\|ValidateLifetime\|RequireExpirationTime" --include=*.cs` for lifetimes.
- `$AUDIT_CORE_ROOT/skills/audit-code-scan/scripts/grep_scan.py` with `scripts/patterns/dotnet.json`.
- `scan_secrets.py` is client-focused; server-side secrets belong to `audit-secrets-and-config`.

## References
Microsoft docs "JWT bearer authentication", "Use cookie authentication without ASP.NET Core Identity", "Refresh tokens" (Duende/OpenIddict); OWASP Session Management cheat sheet. CWE-613, CWE-522, CWE-384; ASVS 3.2-3.5; OWASP A07:2021. Sibling skills: `audit-authz-and-access-control`, `audit-security-headers-and-middleware`, `audit-secrets-and-config`.
