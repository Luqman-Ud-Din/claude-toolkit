using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Shop.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class AuthController : ControllerBase
{
    // Negative: login must be anonymous. Must NOT be flagged as "missing auth".
    [AllowAnonymous]
    [HttpPost("login")]
    public IActionResult Login([FromBody] LoginRequest req) => Ok(new { token = "..." });

    [AllowAnonymous]
    [HttpPost("forgot-password")]
    public IActionResult ForgotPassword([FromBody] string email) => Accepted();
}

public class LoginRequest { public string Email { get; set; } = ""; public string Password { get; set; } = ""; }
