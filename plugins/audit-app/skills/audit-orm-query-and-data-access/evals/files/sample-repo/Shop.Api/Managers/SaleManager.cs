using Microsoft.EntityFrameworkCore;
using Shop.Api.Data;

namespace Shop.Api.Managers;

public class SaleManager
{
    private readonly ShopDbContext _db;
    public SaleManager(ShopDbContext db) => _db = db;

    // ORM (NPLUS1): one product query per sale line.
    public async Task<decimal> CalculateTotalAsync(int saleId)
    {
        var sale = await _db.Sales.Include(s => s.Lines).FirstAsync(s => s.Id == saleId);
        decimal total = 0;
        foreach (var line in sale.Lines)
        {
            var product = await _db.Products.FirstAsync(p => p.Id == line.ProductId);
            total += product.Price * line.Qty;
        }
        return total;
    }

    // ORM (INEFFICIENT): Count() > 0 instead of Any().
    public bool HasSalesToday(int companyId)
    {
        return _db.Sales.Count(s => s.CompanyId == companyId && s.CreatedAt >= DateTime.UtcNow.Date) > 0;
    }

    // ORM (TXN): sale, lines and stock movements written in two SaveChanges with no transaction.
    public async Task<int> PostAsync(Sale sale)
    {
        _db.Sales.Add(sale);
        await _db.SaveChangesAsync();
        foreach (var line in sale.Lines)
            _db.StockMovements.Add(new StockMovement { ProductId = line.ProductId, Qty = -line.Qty });
        await _db.SaveChangesAsync();
        return sale.Id;
    }

    // OK: batch load then in-memory lookup - must NOT be flagged as N+1.
    public async Task<decimal> CalculateTotalBatchedAsync(int saleId)
    {
        var sale = await _db.Sales.AsNoTracking().Include(s => s.Lines).FirstAsync(s => s.Id == saleId);
        var ids = sale.Lines.Select(l => l.ProductId).ToList();
        var prices = await _db.Products.AsNoTracking()
            .Where(p => ids.Contains(p.Id))
            .Select(p => new { p.Id, p.Price })
            .ToDictionaryAsync(p => p.Id, p => p.Price);
        return sale.Lines.Sum(l => prices[l.ProductId] * l.Qty);
    }
}
