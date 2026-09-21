using System.ComponentModel.DataAnnotations;

namespace Shop.Api.Dtos;

public record AccountDto(int Id, string Name, decimal Balance);
public record TokenDto(string Token);
public record PagedResult<T>(IReadOnlyList<T> Items, int PageNumber, int PageSize);

public class PageQuery
{
    [Range(1, int.MaxValue)] public int PageNumber { get; set; } = 1;
    [Range(1, 100)] public int PageSize { get; set; } = 20;
}

public class LoginRequest
{
    [Required, EmailAddress] public string Email { get; set; } = "";
    [Required] public string Password { get; set; } = "";
}

public class UserProfileDto
{
    public int Id { get; set; }
    public string Email { get; set; } = "";
    public string PasswordHash { get; set; } = "";
}
