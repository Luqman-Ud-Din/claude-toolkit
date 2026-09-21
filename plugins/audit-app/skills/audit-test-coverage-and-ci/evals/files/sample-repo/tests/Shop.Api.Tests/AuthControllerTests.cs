using Microsoft.AspNetCore.Mvc;
using NSubstitute;
using Shop.Api.Controllers;
using Shop.Api.Services;
using Xunit;

namespace Shop.Api.Tests;

public class AuthControllerTests
{
    private readonly IUserStore _users = Substitute.For<IUserStore>();

    private AuthController CreateSut()
    {
        _users.FindAsync("ana@example.com", Arg.Any<CancellationToken>())
            .Returns(("hash", "Admin"));
        var tokens = new TokenService(_users, (password, hash) => password == "correct" && hash == "hash");
        return new AuthController(tokens);
    }

    [Fact]
    public async Task Login_returns_401_for_wrong_password()
    {
        var result = await CreateSut().Login(new LoginRequest("ana@example.com", "wrong"), CancellationToken.None);
        Assert.IsType<UnauthorizedResult>(result);
    }

    [Fact]
    public async Task Login_returns_401_for_unknown_user()
    {
        var result = await CreateSut().Login(new LoginRequest("nobody@example.com", "correct"), CancellationToken.None);
        Assert.IsType<UnauthorizedResult>(result);
    }

    [Fact]
    public async Task TokenService_issues_token_for_valid_credentials()
    {
        CreateSut();
        var tokens = new TokenService(_users, (p, h) => p == "correct" && h == "hash");
        var token = await tokens.IssueAsync("ana@example.com", "correct", CancellationToken.None);
        Assert.NotNull(token);
    }
}
