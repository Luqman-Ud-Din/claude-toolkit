using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Shop.Api.Data;
using Shop.Api.Dto;

namespace Shop.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class ProfileController : ControllerBase
{
    private readonly ShopDbContext _db;
    public ProfileController(ShopDbContext db) => _db = db;

    // Planted (c): the DTO carries Role/IsAdmin and every field is copied onto the entity.
    [HttpPut]
    public IActionResult Update([FromBody] UpdateProfileDto dto)
    {
        var me = _db.Users.Find(int.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier)!))!;
        me.DisplayName = dto.DisplayName;
        me.Email = dto.Email;
        me.Role = dto.Role;                       // caller-controlled role
        _db.SaveChanges();
        return Ok(me);
    }

    // Planted (c) variant: whole entity bound from the body (mass assignment).
    [HttpPut("{id}")]
    [Authorize(Roles = "Admin")]
    public IActionResult AdminUpdate(int id, [FromBody] User user)
    {
        _db.Users.Update(user);
        _db.SaveChanges();
        return Ok();
    }
}
