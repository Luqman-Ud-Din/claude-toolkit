using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Shop.Api.Dtos;

namespace Shop.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class AccountsController : ControllerBase
{
    private readonly ShopDbContext _db;
    public AccountsController(ShopDbContext db) => _db = db;

    // Planted: anonymous endpoint.
    [AllowAnonymous]
    [HttpPost("login")]
    public async Task<ActionResult<TokenDto>> Login([FromBody] LoginRequest request)
    {
        var user = await _db.Users.FirstOrDefaultAsync(u => u.Email == request.Email);
        return user is null ? Unauthorized(new { error = "invalid" }) : Ok(new TokenDto("..."));
    }

    // Planted: unpaginated collection.
    [HttpGet]
    public async Task<ActionResult<List<AccountDto>>> GetAll(int branchId)
    {
        var rows = await _db.Accounts.Where(a => a.BranchId == branchId)
            .Select(a => new AccountDto(a.Id, a.Name, a.Balance))
            .ToListAsync();
        return Ok(rows);
    }

    // Planted: paginated collection.
    [HttpGet("page")]
    public async Task<ActionResult<PagedResult<AccountDto>>> GetPage([FromQuery] PageQuery query)
    {
        var items = await _db.Accounts.OrderBy(a => a.Name)
            .Skip((query.PageNumber - 1) * query.PageSize).Take(query.PageSize)
            .Select(a => new AccountDto(a.Id, a.Name, a.Balance))
            .ToListAsync();
        return Ok(new PagedResult<AccountDto>(items, query.PageNumber, query.PageSize));
    }

    // Planted: ownership check present (caller claim in the predicate).
    [HttpGet("{id:int}")]
    public async Task<ActionResult<AccountDto>> Get(int id)
    {
        var ownerId = int.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier)!);
        var a = await _db.Accounts.FirstOrDefaultAsync(x => x.Id == id && x.OwnerId == ownerId);
        return a is null ? NotFound(new { error = "not found" }) : Ok(new AccountDto(a.Id, a.Name, a.Balance));
    }

    // Planted: ownership check absent (route id only).
    [HttpGet("{id:int}/statement")]
    public async Task<ActionResult<AccountDto>> Statement(int id)
    {
        var a = await _db.Accounts.FindAsync(id);
        return a is null ? NotFound(new { error = "not found" }) : Ok(new AccountDto(a.Id, a.Name, a.Balance));
    }

    // Planted: response DTO exposing PasswordHash.
    [HttpGet("{id:int}/profile")]
    public async Task<ActionResult<UserProfileDto>> Profile(int id)
    {
        var ownerId = int.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier)!);
        var u = await _db.Users.FirstAsync(x => x.Id == id && x.Id == ownerId);
        return Ok(new UserProfileDto { Id = u.Id, Email = u.Email, PasswordHash = u.PasswordHash });
    }
}
