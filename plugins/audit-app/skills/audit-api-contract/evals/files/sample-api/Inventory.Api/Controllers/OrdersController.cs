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
[Route("api/v{version:apiVersion}/orders")]
public class OrdersController : ControllerBase
{
    private readonly InventoryDbContext _db;

    public OrdersController(InventoryDbContext db) => _db = db;

    [HttpGet]
    public async Task<ActionResult<PagedResult<OrderDto>>> List([FromQuery] PageQuery query, CancellationToken ct)
    {
        var companyId = int.Parse(User.FindFirst("company_id")!.Value);
        var size = Math.Clamp(query.PageSize, 1, 100);
        var orders = _db.Orders.Where(o => o.CompanyId == companyId);
        var items = await orders.OrderByDescending(o => o.CreatedAt)
            .Skip((query.Page - 1) * size).Take(size)
            .Select(o => new OrderDto(o.Id, o.Number, o.Total, o.Status, o.CreatedAt))
            .ToListAsync(ct);
        return new PagedResult<OrderDto>(items, await orders.CountAsync(ct), query.Page, size);
    }

    [HttpGet("{id:guid}")]
    public async Task<ActionResult<OrderDto>> Get(Guid id, CancellationToken ct)
    {
        var companyId = int.Parse(User.FindFirst("company_id")!.Value);
        var o = await _db.Orders.FirstOrDefaultAsync(x => x.Id == id && x.CompanyId == companyId, ct);
        if (o is null)
            return Problem(statusCode: StatusCodes.Status404NotFound, title: "Order not found");
        return new OrderDto(o.Id, o.Number, o.Total, o.Status, o.CreatedAt);
    }

    [HttpPost]
    public async Task<ActionResult<OrderDto>> Create([FromBody] CreateOrderRequest request, CancellationToken ct)
    {
        var companyId = int.Parse(User.FindFirst("company_id")!.Value);
        if (request.Lines.Any(l => l.Quantity <= 0))
        {
            ModelState.AddModelError(nameof(request.Lines), "Quantity must be greater than 0");
            return ValidationProblem(ModelState);
        }

        var order = new Order
        {
            Id = Guid.NewGuid(), Number = $"SO-{DateTimeOffset.UtcNow:yyyyMMddHHmmss}",
            CompanyId = companyId, BranchId = request.BranchId,
            Status = OrderStatus.Pending, CreatedAt = DateTimeOffset.UtcNow
        };
        _db.Orders.Add(order);
        await _db.SaveChangesAsync(ct);
        var dto = new OrderDto(order.Id, order.Number, order.Total, order.Status, order.CreatedAt);
        return CreatedAtAction(nameof(Get), new { id = order.Id, version = "1.0" }, dto);
    }

    [HttpPost("{id:guid}/cancel")]
    public async Task<IActionResult> Cancel(Guid id, CancellationToken ct)
    {
        var companyId = int.Parse(User.FindFirst("company_id")!.Value);
        var order = await _db.Orders.FirstOrDefaultAsync(x => x.Id == id && x.CompanyId == companyId, ct);
        if (order is null)
            return Problem(statusCode: StatusCodes.Status404NotFound, title: "Order not found");
        if (order.Status != OrderStatus.Pending)
            return Problem(statusCode: StatusCodes.Status409Conflict, title: "Only pending orders can be cancelled");
        order.Status = OrderStatus.Cancelled;
        await _db.SaveChangesAsync(ct);
        return NoContent();
    }
}
