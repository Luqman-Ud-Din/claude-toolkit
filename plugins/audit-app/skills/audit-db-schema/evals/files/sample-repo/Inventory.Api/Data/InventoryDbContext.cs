using Microsoft.EntityFrameworkCore;
using Inventory.Api.Data.Entities;

namespace Inventory.Api.Data
{
    public class InventoryDbContext : DbContext
    {
        public InventoryDbContext(DbContextOptions<InventoryDbContext> options) : base(options) { }

        public DbSet<Product> Products { get; set; }
        public DbSet<Order> Orders { get; set; }
        public DbSet<OrderLine> OrderLines { get; set; }
        public DbSet<User> Users { get; set; }

        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            modelBuilder.Entity<Product>()
                .Property(p => p.SalePrice).HasPrecision(18, 4);
            modelBuilder.Entity<Product>()
                .HasIndex(p => new { p.CompanyId, p.Sku }).IsUnique();
            modelBuilder.Entity<Product>()
                .HasQueryFilter(p => !p.IsDeleted);

            modelBuilder.Entity<Order>()
                .HasIndex(o => new { o.CompanyId, o.BranchId, o.CreatedAt });
            modelBuilder.Entity<Order>()
                .HasQueryFilter(o => !o.IsDeleted);

            modelBuilder.Entity<User>()
                .HasQueryFilter(u => !u.IsDeleted);
            modelBuilder.Entity<User>()
                .HasIndex(u => new { u.CompanyId, u.Email }).IsUnique();

            modelBuilder.Entity<OrderLine>()
                .HasOne(l => l.Order).WithMany(o => o.Lines).HasForeignKey(l => l.OrderId).OnDelete(DeleteBehavior.Cascade);
        }
    }
}
