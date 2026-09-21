using Microsoft.EntityFrameworkCore;
using Inventory.Api.Data;
using Inventory.Api.Models;

namespace Inventory.Api.Repositories;

public class ProductRepository
{
    private readonly InventoryDbContext _context;

    public ProductRepository(InventoryDbContext context)
    {
        _context = context;
    }

    // SAFE (must NOT be flagged): {0} placeholder with a parameter argument.
    // EF Core sends sku as @p0; the value never enters the SQL text.
    public Task<Product?> GetBySkuAsync(string sku)
    {
        return _context.Products
            .FromSqlRaw("SELECT * FROM Products WHERE Sku = {0}", sku)
            .FirstOrDefaultAsync();
    }

    // SAFE (must NOT be flagged): FromSqlInterpolated turns the interpolation holes
    // into DbParameters.
    public Task<List<Product>> GetByBranchAsync(int branchId, int companyId)
    {
        return _context.Products
            .FromSqlInterpolated($"SELECT * FROM Products WHERE BranchId = {branchId} AND CompanyId = {companyId}")
            .ToListAsync();
    }
}
