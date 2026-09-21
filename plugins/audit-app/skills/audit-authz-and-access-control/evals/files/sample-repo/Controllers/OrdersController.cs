using System.Security.Claims;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Shop.Api.Data;
using Shop.Api.Dto;

namespace Shop.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class OrdersController : ControllerBase
{
    private readonly ShopDbContext _db;
    public OrdersController(ShopDbContext db) => _db = db;

    private int CallerId => int.Parse(User.FindFirstValue(ClaimTypes.NameIdentifier)!);

    // Negative: list is scoped to the caller. Must NOT be flagged for IDOR.
    [HttpGet]
    public IActionResult Mine() => Ok(_db.Orders.Where(o => o.CustomerId == CallerId).ToList());

    // Planted (b): loads by route id only; any authenticated user can read any order.
    [HttpGet("{id}")]
    public IActionResult Get(int id)
    {
        var order = _db.Orders.Find(id);
        return order is null ? NotFound() : Ok(order);
    }

    // Planted (b): same defect on a write path; deletes any order by id.
    [HttpDelete("{id}")]
    public IActionResult Delete(int id)
    {
        var order = _db.Orders.FirstOrDefault(o => o.Id == id);
        if (order is null) return NotFound();
        _db.Orders.Remove(order);
        _db.SaveChanges();
        return NoContent();
    }

    // Negative: ownership enforced in the predicate. Must NOT be flagged.
    [HttpGet("{id}/receipt")]
    public IActionResult Receipt(int id)
    {
        var order = _db.Orders.FirstOrDefault(o => o.Id == id && o.CustomerId == CallerId);
        return order is null ? NotFound() : Ok(new { order.Id, order.Total });
    }

    [HttpPost]
    public IActionResult Create([FromBody] CreateOrderDto dto)
    {
        var order = new Order { CustomerId = CallerId, Total = dto.Total };
        _db.Orders.Add(order);
        _db.SaveChanges();
        return CreatedAtAction(nameof(Get), new { id = order.Id }, order);
    }

    // Negative: role enforced server-side. Must NOT be flagged.
    [Authorize(Roles = "Admin")]
    [HttpGet("all")]
    public IActionResult All() => Ok(_db.Orders.ToList());
}
