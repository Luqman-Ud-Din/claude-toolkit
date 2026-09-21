using Asp.Versioning;
using Inventory.Api.Data;
using Inventory.Api.Dtos;
using Inventory.Api.Entities;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace Inventory.Api.Controllers;

[ApiController]
[ApiVersion("1.0")]
[Authorize]
[Route("api/v{version:apiVersion}/users")]
public class UsersController : ControllerBase
{
    private readonly InventoryDbContext _db;

    public UsersController(InventoryDbContext db) => _db = db;

    [HttpGet]
    public async Task<ActionResult<PagedResult<UserSummaryDto>>> List([FromQuery] PageQuery query, CancellationToken ct)
    {
        var companyId = int.Parse(User.FindFirst("company_id")!.Value);
        var size = Math.Clamp(query.PageSize, 1, 100);
        var users = _db.Users.Where(u => u.CompanyId == companyId && !u.IsDeleted);
        var items = await users.OrderBy(u => u.Email)
            .Skip((query.Page - 1) * size).Take(size)
            .Select(u => new UserSummaryDto(u.Id, u.Email, u.DisplayName, u.Role))
            .ToListAsync(ct);
        return new PagedResult<UserSummaryDto>(items, await users.CountAsync(ct), query.Page, size);
    }

    [HttpGet("{id:int}")]
    public async Task<ActionResult<User>> Get(int id, CancellationToken ct)
    {
        var companyId = int.Parse(User.FindFirst("company_id")!.Value);
        var user = await _db.Users.FirstOrDefaultAsync(u => u.Id == id && u.CompanyId == companyId, ct);
        if (user is null)
            return Problem(statusCode: StatusCodes.Status404NotFound, title: "User not found");
        return Ok(user);
    }
}
