using Microsoft.EntityFrameworkCore;

namespace Orders.Api.Data
{
    public class Order { public int Id { get; set; } public int CustomerId { get; set; } public decimal Total { get; set; } }
    public class Invoice { public int Id { get; set; } public int OrderId { get; set; } public decimal Amount { get; set; } public string Status { get; set; } = ""; }

    public class OrdersDbContext : DbContext
    {
        public OrdersDbContext(DbContextOptions<OrdersDbContext> o) : base(o) { }
        public DbSet<Order> Orders { get; set; }
        public DbSet<Invoice> Invoices { get; set; }
    }
}
