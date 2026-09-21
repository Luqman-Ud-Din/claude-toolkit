using Asp.Versioning;
using Inventory.Api.Data;
using Inventory.Api.Dtos;
using Inventory.Api.Entities;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace Inventory.Api.Controllers;

[ApiController]
[ApiVersion("1.0")]
[Authorize]
[Route("api/v{version:apiVersion}/products")]
public class ProductsController : ControllerBase
{
    private readonly InventoryDbContext _db;

    public ProductsController(InventoryDbContext db) => _db = db;

    // Returns every product in the table on every call.
    [HttpGet]
    public async Task<ActionResult<List<ProductDto>>> GetAll(CancellationToken ct)
    {
        var companyId = int.Parse(User.FindFirst("company_id")!.Value);
        var products = await _db.Products
            .Where(p => p.CompanyId == companyId && !p.IsDeleted)
            .OrderBy(p => p.Name)
            .Select(p => new ProductDto(p.Id, p.Sku, p.Name, p.Price))
            .ToListAsync(ct);
        return Ok(products);
    }

    [HttpGet("{id:int}")]
    public async Task<ActionResult<ProductDto>> GetById(int id, CancellationToken ct)
    {
        var companyId = int.Parse(User.FindFirst("company_id")!.Value);
        var p = await _db.Products.FirstOrDefaultAsync(x => x.Id == id && x.CompanyId == companyId, ct);
        if (p is null)
            return NotFound(new { error = "Product not found" });
        return Ok(new ProductDto(p.Id, p.Sku, p.Name, p.Price));
    }

    [HttpPost]
    public async Task<ActionResult<ProductDto>> Create([FromBody] CreateProductRequest request, CancellationToken ct)
    {
        var companyId = int.Parse(User.FindFirst("company_id")!.Value);
        if (await _db.Products.AnyAsync(x => x.Sku == request.Sku && x.CompanyId == companyId, ct))
            return BadRequest(new { error = $"SKU {request.Sku} already exists" });

        var product = new Product
        {
            Sku = request.Sku, Name = request.Name, Price = request.Price,
            CostPrice = request.CostPrice, CompanyId = companyId
        };
        _db.Products.Add(product);
        await _db.SaveChangesAsync(ct);
        return CreatedAtAction(nameof(GetById), new { id = product.Id, version = "1.0" },
            new ProductDto(product.Id, product.Sku, product.Name, product.Price));
    }
}
