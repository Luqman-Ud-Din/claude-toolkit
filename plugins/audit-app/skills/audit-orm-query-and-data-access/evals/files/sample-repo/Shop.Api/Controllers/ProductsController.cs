using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Shop.Api.Data;

namespace Shop.Api.Controllers;

public record ProductDto(int Id, string Name, decimal Price);
public record PageRequest(int PageNumber = 1, int PageSize = 20, string? SearchTerm = null);

[ApiController]
[Route("api/[controller]")]
public class ProductsController : ControllerBase
{
    private readonly ShopDbContext _db;
    public ProductsController(ShopDbContext db) => _db = db;

    // ORM (UNBOUNDED + TRACKING): whole table, tracked, full entities, no paging.
    [HttpGet]
    public async Task<IActionResult> GetAll(int companyId)
    {
        var products = await _db.Products.Where(p => p.CompanyId == companyId && !p.IsDeleted).ToListAsync();
        return Ok(products);
    }

    // ORM (INDEX): filter on Name with a leading wildcard - no index on Name (see ShopDbContext).
    [HttpGet("search")]
    public async Task<IActionResult> Search(int companyId, string term)
    {
        var products = await _db.Products.AsNoTracking()
            .Where(p => p.CompanyId == companyId && p.Name.Contains(term))
            .Take(50).ToListAsync();
        return Ok(products);
    }

    // OK: paged, no-tracking, projected - must NOT be flagged.
    [HttpPost("page")]
    public async Task<IActionResult> GetPage(int companyId, [FromBody] PageRequest req)
    {
        var size = Math.Min(req.PageSize, 100);
        var q = _db.Products.AsNoTracking().Where(p => p.CompanyId == companyId && !p.IsDeleted);
        var total = await q.CountAsync();
        var items = await q.OrderBy(p => p.Name)
            .Skip((req.PageNumber - 1) * size).Take(size)
            .Select(p => new ProductDto(p.Id, p.Name, p.Price))
            .ToListAsync();
        return Ok(new { total, items });
    }

    // OK: Any() instead of Count() > 0 - must NOT be flagged.
    [HttpGet("exists")]
    public async Task<IActionResult> Exists(int companyId, string sku)
        => Ok(await _db.Products.AnyAsync(p => p.CompanyId == companyId && p.Sku == sku));
}
