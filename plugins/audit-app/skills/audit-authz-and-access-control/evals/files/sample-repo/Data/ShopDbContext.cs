using Microsoft.EntityFrameworkCore;

namespace Shop.Api.Data;

public class Order { public int Id { get; set; } public int CustomerId { get; set; } public decimal Total { get; set; } }
public class User { public int Id { get; set; } public string Email { get; set; } = ""; public string Role { get; set; } = "Customer"; public string DisplayName { get; set; } = ""; }

public class ShopDbContext : DbContext
{
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<User> Users => Set<User>();
}
