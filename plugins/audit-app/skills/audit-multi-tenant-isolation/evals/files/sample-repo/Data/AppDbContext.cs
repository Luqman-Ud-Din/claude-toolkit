using Microsoft.EntityFrameworkCore;
using Saas.Api.Infrastructure;

namespace Saas.Api.Data;

public class Invoice { public int Id { get; set; } public int TenantId { get; set; } public decimal Total { get; set; } public string Number { get; set; } = ""; }
public class Document { public int Id { get; set; } public int TenantId { get; set; } public string BlobPath { get; set; } = ""; }

public class AppDbContext : DbContext
{
    private readonly ITenantContext _tenant;
    public AppDbContext(DbContextOptions<AppDbContext> o, ITenantContext tenant) : base(o) => _tenant = tenant;

    public DbSet<Invoice> Invoices => Set<Invoice>();
    public DbSet<Document> Documents => Set<Document>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        // Global tenant filter: EF Core LINQ queries are scoped automatically.
        b.Entity<Invoice>().HasQueryFilter(i => i.TenantId == _tenant.TenantId);
        b.Entity<Document>().HasQueryFilter(d => d.TenantId == _tenant.TenantId);
    }
}
