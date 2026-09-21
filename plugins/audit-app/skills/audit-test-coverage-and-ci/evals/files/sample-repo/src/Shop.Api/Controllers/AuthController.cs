using Microsoft.AspNetCore.Mvc;
using Shop.Api.Services;

namespace Shop.Api.Controllers;

public record LoginRequest(string Email, string Password);

[ApiController]
[Route("api/auth")]
public class AuthController : ControllerBase
{
    private readonly TokenService _tokens;

    public AuthController(TokenService tokens) => _tokens = tokens;

    [HttpPost("login")]
    public async Task<IActionResult> Login([FromBody] LoginRequest request, CancellationToken ct)
    {
        var token = await _tokens.IssueAsync(request.Email, request.Password, ct);
        return token is null ? Unauthorized() : Ok(new { token });
    }
}
