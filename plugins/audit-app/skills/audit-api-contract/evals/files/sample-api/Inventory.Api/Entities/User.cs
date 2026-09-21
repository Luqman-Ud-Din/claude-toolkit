namespace Inventory.Api.Entities;

public class User
{
    public int Id { get; set; }
    public string Email { get; set; } = "";
    public string DisplayName { get; set; } = "";
    public string PasswordHash { get; set; } = "";
    public string SecurityStamp { get; set; } = "";
    public int CompanyId { get; set; }
    public string Role { get; set; } = "Customer";
    public bool IsDeleted { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
}
