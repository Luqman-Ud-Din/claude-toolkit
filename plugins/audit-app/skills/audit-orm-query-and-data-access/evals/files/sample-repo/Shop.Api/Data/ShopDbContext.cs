using Microsoft.EntityFrameworkCore;

namespace Shop.Api.Data;

public class Product { public int Id { get; set; } public int CompanyId { get; set; } public string Name { get; set; } = ""; public string Sku { get; set; } = ""; public decimal Price { get; set; } public bool IsDeleted { get; set; } }
public class Sale { public int Id { get; set; } public int CompanyId { get; set; } public DateTime CreatedAt { get; set; } public List<SaleLine> Lines { get; set; } = new(); }
public class SaleLine { public int Id { get; set; } public int SaleId { get; set; } public int ProductId { get; set; } public int Qty { get; set; } public decimal Total { get; set; } }
public class StockMovement { public int Id { get; set; } public int ProductId { get; set; } public int Qty { get; set; } }

public class ShopDbContext : DbContext
{
    public ShopDbContext(DbContextOptions<ShopDbContext> o) : base(o) { }
    public DbSet<Product> Products => Set<Product>();
    public DbSet<Sale> Sales => Set<Sale>();
    public DbSet<SaleLine> SaleLines => Set<SaleLine>();
    public DbSet<StockMovement> StockMovements => Set<StockMovement>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        b.Entity<Product>().HasIndex(p => new { p.CompanyId, p.Sku });   // no index on Name (used by Search)
        b.Entity<Sale>().HasIndex(s => s.CompanyId);
    }
}
