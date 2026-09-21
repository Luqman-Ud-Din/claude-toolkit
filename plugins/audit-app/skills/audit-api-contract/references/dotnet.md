# .NET / C# reference for audit-api-contract

## Stack markers
`*.csproj`, `*.sln`, `Program.cs`. Variants: controllers (`[ApiController]`) vs minimal APIs (`MapGet`/`MapPost`); Swashbuckle vs NSwag vs built-in `Microsoft.AspNetCore.OpenApi`; `Asp.Versioning` (formerly `Microsoft.AspNetCore.Mvc.Versioning`); Ocelot/YARP gateway (routes may be rewritten there: `ocelotconfig.json` upstream vs downstream templates).

## Where the relevant code lives
- Spec: `Program.cs`/`Startup.cs` (`AddSwaggerGen`, `UseSwagger`, `UseSwaggerUI`, `MapOpenApi`, `MapScalarApiReference`), `swagger.json` in repo, gateway `ocelotconfig.json` (`SwaggerEndPoints`).
- Routes: `[Route("api/[controller]")]`, `[HttpGet("...")]`, `[ApiVersion("1.0")]`, `[Route("api/v{version:apiVersion}/...")]`, minimal API `MapGroup`.
- DTOs: `*Dto.cs`, `HostModel/`, `Models/Request*`; validation via DataAnnotations (`[Required]`, `[Range]`, `[StringLength]`, `[EmailAddress]`, `[RegularExpression]`) or FluentValidation `AbstractValidator<T>`.
- Errors: `UseExceptionHandler`, `IExceptionHandler` (.NET 8), `ProblemDetails`/`AddProblemDetails()`, `[ApiController]` automatic 400 (`ValidationProblemDetails`), custom `ExceptionFilterAttribute`.
- Pagination: `Skip`/`Take`, `PagedList<T>`, `DataTableAjaxPostModel`, `PaginationModel`.
- Serialisation: `AddJsonOptions` (`PropertyNamingPolicy`, `JsonStringEnumConverter`, `ReferenceHandler`), Newtonsoft `AddNewtonsoftJson`.

## Dangerous / interesting APIs and patterns
- Spec exposure: `app.UseSwagger(); app.UseSwaggerUI();` outside `if (app.Environment.IsDevelopment())`; `MapOpenApi()` unconditionally; Ocelot exposing downstream swagger; no `[Authorize]` or middleware on `/swagger`.
- Entity returned: `ActionResult<User>`, `IEnumerable<Order>`, `return Ok(entity)`, `_db.Users.ToList()` with no `.Select(...)`; entity classes with `PasswordHash`, `Salt`, `SecurityStamp`, `RefreshToken`, `ApiKey`, `Otp`, `IsDeleted`, `CompanyId` and no `[JsonIgnore]`.
- Unpaginated: `[HttpGet]` returning `ToList()`/`ToListAsync()` with no `Skip`/`Take`; `GetAll`, `List` methods; `DataTableAjaxPostModel` with `Length = -1` accepted.
- Validation: request classes with no attributes; `[FromBody]` binding to an entity; controllers without `[ApiController]` (no automatic 400) and no `ModelState.IsValid` check; `[Range]` missing on quantities/prices; `[MaxLength]` missing on strings persisted to `nvarchar(max)`.
- Error shape: `return BadRequest(new { error = ... })`, `return StatusCode(500, ex.Message)`, `Ok(new { success = false, message })`, `throw` without a global handler, `ex.StackTrace` in responses; mix of `ProblemDetails` and anonymous objects across controllers.
- Status codes: `return Ok()` on create; `return Ok()` for not-found (`null` -> 204 with `[ApiController]`? no: returns 204 only for `NoContent`; `Ok(null)` gives 200 empty); `Unauthorized()` used for forbidden; `BadRequest` for conflicts.
- Naming/dates: `PropertyNamingPolicy = null` (PascalCase JSON), `DateTime` properties without `Kind`/offset (serialised without `Z`), enums as ints (no `JsonStringEnumConverter`), `[JsonPropertyName]` inconsistencies.
- Versioning: no `AddApiVersioning`; mixed `api/v1/` and `api/` routes; `[Obsolete]` on actions without a `Sunset` header.

## What "good" looks like
```csharp
if (app.Environment.IsDevelopment()) { app.UseSwagger(); app.UseSwaggerUI(); }   // or behind [Authorize] middleware
builder.Services.AddProblemDetails(); app.UseExceptionHandler();                // RFC 9457 everywhere
builder.Services.AddApiVersioning(o => { o.DefaultApiVersion = new(1, 0); o.ReportApiVersions = true; })
                .AddMvc().AddApiExplorer(o => o.GroupNameFormat = "'v'VVV");
[ApiController] [ApiVersion("1.0")] [Route("api/v{version:apiVersion}/orders")]
public class OrdersController : ControllerBase {
    [HttpGet] public async Task<ActionResult<PagedResult<OrderDto>>> List([FromQuery] PageQuery q, CancellationToken ct) {
        var size = Math.Clamp(q.PageSize, 1, 100);
        var query = _db.Orders.Where(o => o.CompanyId == _tenant.Id);
        var items = await query.OrderByDescending(o => o.CreatedAt).Skip((q.Page - 1) * size).Take(size)
                               .Select(o => new OrderDto(o.Id, o.Number, o.Total, o.CreatedAt)).ToListAsync(ct);
        return new PagedResult<OrderDto>(items, await query.CountAsync(ct), q.Page, size);
    }
    [HttpPost] public async Task<ActionResult<OrderDto>> Create([FromBody] CreateOrderRequest req, CancellationToken ct) { ...; return CreatedAtAction(nameof(Get), new { id }, dto); }
}
public record CreateOrderRequest([Required, MinLength(1)] List<LineRequest> Lines, [StringLength(32)] string? CouponCode);
```
`AddJsonOptions(o => { o.JsonSerializerOptions.PropertyNamingPolicy = JsonNamingPolicy.CamelCase; o.JsonSerializerOptions.Converters.Add(new JsonStringEnumConverter()); })`; `DateTimeOffset` on DTOs.

## Manual trace checklist
1. `Program.cs`: Swagger/OpenAPI registration and its environment guard; `AddProblemDetails`/`UseExceptionHandler`; `AddApiVersioning`; JSON options.
2. Endpoint table: for each `[HttpGet]` returning a collection, find `Skip/Take` or `PagedList`; for each action returning an entity type, list the entity's fields.
3. Every `[FromBody]` type: attributes present; not an entity.
4. Every `BadRequest(`/`StatusCode(`/`Ok(new {` with an anonymous object: collect shapes per controller.
5. Ocelot/YARP config: upstream paths vs downstream, version segments dropped or added by the gateway.
6. Spec diff: previous `swagger.json` from git (`git show <tag>:path/swagger.json`) vs current (`dotnet swagger tofile` if the CLI is installed).

## Stack-specific false positives
- `ActionResult<Entity>` where the entity has no sensitive fields and no navigation properties (still recommend a DTO, rate Info).
- `Ok(new { id })` for a trivial create response (naming/Info only).
- Swagger mounted in production behind an authenticated reverse proxy (confirm with the user, record the control).
- `DataTableAjaxPostModel` lists with a server-side length clamp in `CommonFunction.PaginationAssign`.

## Tooling
`dotnet swagger tofile --output swagger.json <dll> v1` (Swashbuckle CLI); `grep -rn "UseSwagger\|MapOpenApi" --include=*.cs`; `grep -rn "ActionResult<\(User\|Order\|Product\)\b" --include=*.cs`; `$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py`; `oasdiff breaking old.json new.json` if installed, else `scripts/spec_diff.py`.

## References
ASVS 13.1/13.2, OWASP API Security Top 10 2023 (API3, API4, API8, API9), RFC 9457, Microsoft REST API guidelines, `Asp.Versioning` docs.
