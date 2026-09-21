# .NET / ASP.NET Core reference for audit-authz-and-access-control

## Stack markers
`*.csproj`, `*.sln`, `Program.cs` / `Startup.cs`, `Controllers/`. Variants: MVC/API controllers vs minimal APIs; Ocelot/YARP gateway in front (routes there are pass-through - authorization is still the downstream service's job).

## Where the relevant code lives
`Controllers/*Controller.cs` (action attributes), `Program.cs`/`Startup.cs` (`AddAuthentication`/`AddAuthorization`, `UseAuthorization`, fallback policy), `*Manager.cs`/`*Service.cs` (the actual data queries where ownership must be enforced), DTOs under `*.Dto`/`HostModel`, `BackgroundJobs/` (jobs bypass HTTP auth entirely).

## Dangerous / interesting APIs and patterns
- Missing auth: a `ControllerBase` subclass with no `[Authorize]` on the class and none on the action, and no `[AllowAnonymous]` marking it deliberate. Global fallback: `AddAuthorization(o => o.FallbackPolicy = ...)` or `MapControllers().RequireAuthorization()` flips the default - check for it before flagging.
- `[AllowAnonymous]` - always intentional? Fine for login/register/forgot-password/health; a hole anywhere else.
- IDOR: `_db.X.Find(id)` / `FindAsync(id)` / `FirstOrDefault(x => x.Id == id)` where the predicate does NOT also compare `CompanyId`/`BranchId`/`UserId`/`CustomerId` against the caller's claim. In this codebase the caller's identity comes from `_identityService.GetClaimDetail()` and tenant from `CustomConnectionString.DbName`.
- Mass assignment / privilege escalation: a bound request shape (`[FromBody] Dto`) that carries `Role`/`Roles`/`IsAdmin`/`Permission` fields, or `[FromBody] Entity` binding a domain entity directly. Then `_db.Update(entity)` or copying `dto.Role` onto the entity.
- Role enforcement: `[Authorize(Roles = "Admin")]` / `[Authorize(Policy = "...")]` / `IAuthorizationService.AuthorizeAsync(User, resource, requirement)`. Roles checked only in the UI are not enforcement.
- Minimal APIs: `app.MapGet(...)` with no `.RequireAuthorization()` and no fallback policy is anonymous.

## What "good" looks like
```csharp
[Authorize]                                   // class-level default
[HttpGet("{id}")]
public async Task<IActionResult> Get(int id) {
    var order = await _db.Orders
        .FirstOrDefaultAsync(o => o.Id == id && o.CustomerId == _caller.Id);
    return order is null ? NotFound() : Ok(order);   // 404, not 403, to avoid id enumeration
}
```
Bind a request DTO with only editable fields; set `Role` server-side from policy, never from the body.

## Manual trace checklist
1. Any endpoint the inventory marks `auth_required=false` that is not login/register/health - trace to confirm it is truly public.
2. Every handler with an id route parameter - open it, confirm the query filters by the caller's owner/tenant id. This is the highest-value trace.
3. Every "update self" / profile / settings endpoint - confirm the bound shape cannot set role/permission/tenant.
4. Background jobs - they run with no HTTP identity; confirm they set tenant/user context explicitly.

## Stack-specific false positives
`[AllowAnonymous]` on login/register/health; `Find(id)` inside an admin-only (`[Authorize(Roles=...)]`) action where cross-tenant read is the point; a global `FallbackPolicy` that authorizes everything not explicitly anonymous (then a controller with no `[Authorize]` is still protected).

## Tooling
`SecurityCodeScan.VS2019`, `Microsoft.CodeAnalysis.NetAnalyzers`, `dotnet list package --vulnerable`. For live probing use `scripts/authz_probe.py` against a disposable environment.

## References
CWE-306 (missing authn), CWE-862 (missing authz), CWE-863 (incorrect authz), CWE-639 (IDOR), CWE-915 (mass assignment), CWE-602 (client-side enforcement). ASVS 4.1 (general access control), 4.2 (object-level), 1.4 (architecture). OWASP A01:2021 (Broken Access Control).
