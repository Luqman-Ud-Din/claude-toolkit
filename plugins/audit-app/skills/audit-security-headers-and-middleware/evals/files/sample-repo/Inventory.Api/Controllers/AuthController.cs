using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Inventory.Api.Controllers;

[Route("api/[controller]")]
[ApiController]
public class AuthController : ControllerBase
{
    public record LoginRequest(string Username, string Password);

    // No rate limiting on login (no AddRateLimiter/UseRateLimiter anywhere in the pipeline).
    [HttpPost("login")]
    [AllowAnonymous]
    public IActionResult Login([FromBody] LoginRequest request)
    {
        var accessToken = "eyJ.example.token";
        var refreshToken = Guid.NewGuid().ToString("N");

        // ISSUE (planted): refresh cookie without HttpOnly (CookieOptions.HttpOnly defaults to false)
        // and without SameSite; script on the origin can read it.
        Response.Cookies.Append("refresh_token", refreshToken, new CookieOptions
        {
            Secure = true,
            Expires = DateTimeOffset.UtcNow.AddDays(30),
        });

        return Ok(new { accessToken });
    }

    [HttpPost("logout")]
    [Authorize]
    public IActionResult Logout()
    {
        Response.Cookies.Delete("refresh_token");
        return NoContent();
    }
}
