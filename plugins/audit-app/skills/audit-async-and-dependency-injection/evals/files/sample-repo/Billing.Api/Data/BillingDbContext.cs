using Microsoft.EntityFrameworkCore;

namespace Billing.Api.Data;

public class Invoice { public int Id { get; set; } public int CompanyId { get; set; } public decimal Total { get; set; } public string Status { get; set; } = "Draft"; }
public class TaxRate { public int Id { get; set; } public string Region { get; set; } = ""; public decimal Rate { get; set; } }

public class BillingDbContext : DbContext
{
    public BillingDbContext(DbContextOptions<BillingDbContext> o) : base(o) { }
    public DbSet<Invoice> Invoices => Set<Invoice>();
    public DbSet<TaxRate> TaxRates => Set<TaxRate>();
}
