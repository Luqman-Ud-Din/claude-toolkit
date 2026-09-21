namespace Shop.Api.Services;

public interface IUserStore
{
    Task<(string PasswordHash, string Role)?> FindAsync(string email, CancellationToken ct);
}

public class TokenService
{
    private readonly IUserStore _users;
    private readonly Func<string, string, bool> _verifyPassword;

    public TokenService(IUserStore users, Func<string, string, bool> verifyPassword)
    {
        _users = users;
        _verifyPassword = verifyPassword;
    }

    public async Task<string?> IssueAsync(string email, string password, CancellationToken ct)
    {
        var user = await _users.FindAsync(email, ct);
        if (user is null || !_verifyPassword(password, user.Value.PasswordHash))
            return null;
        return $"token-for-{email}-{user.Value.Role}";
    }
}
