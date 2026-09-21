using Microsoft.AspNetCore.Mvc;
using Shop.Api.Data;

namespace Shop.Api.Controllers;

// Planted (a): no authorize attribute on the class or any action, and nothing marking it deliberately anonymous.
[ApiController]
[Route("api/[controller]")]
public class ReportsController : ControllerBase
{
    private readonly ShopDbContext _db;
    public ReportsController(ShopDbContext db) => _db = db;

    [HttpGet("sales-summary")]
    public IActionResult SalesSummary() => Ok(_db.Orders.Sum(o => o.Total));

    [HttpGet("customers")]
    public IActionResult Customers() => Ok(_db.Users.Select(u => new { u.Id, u.Email }).ToList());
}
