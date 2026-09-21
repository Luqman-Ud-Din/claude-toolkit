using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace Inventory.Api.Controllers;

[Route("api/[controller]")]
[ApiController]
[Authorize]
public class OrdersController : ControllerBase
{
    private readonly InventoryDbContext _db;

    public OrdersController(InventoryDbContext db) => _db = db;

    // Tenant scoping: every order row carries CompanyId and BranchId.
    [HttpGet("{id:int}")]
    public async Task<IActionResult> Get(int id, CancellationToken ct)
    {
        var companyId = int.Parse(User.FindFirst("CompanyId")!.Value);
        var order = await _db.Orders.AsNoTracking()
            .FirstOrDefaultAsync(o => o.Id == id && o.CompanyId == companyId, ct);
        return order is null ? NotFound() : Ok(order);
    }

    [HttpPost("{id:int}/pay")]
    public async Task<IActionResult> Pay(int id, CancellationToken ct)
    {
        var companyId = int.Parse(User.FindFirst("CompanyId")!.Value);
        var order = await _db.Orders.FirstAsync(o => o.Id == id && o.CompanyId == companyId, ct);
        order.Status = OrderStatus.Paid;
        await _db.SaveChangesAsync(ct);
        return NoContent();
    }
}
