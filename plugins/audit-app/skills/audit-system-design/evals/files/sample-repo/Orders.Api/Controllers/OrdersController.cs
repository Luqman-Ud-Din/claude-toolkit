using Microsoft.AspNetCore.Mvc;
using Orders.Api.Data;
using Shared.Contracts;

namespace Orders.Api.Controllers
{
    [ApiController]
    [Route("api/[controller]")]
    public class OrdersController : ControllerBase
    {
        private readonly OrdersDbContext _db;
        private readonly IEventPublisher _publisher;

        public OrdersController(OrdersDbContext db, IEventPublisher publisher)
        {
            _db = db;
            _publisher = publisher;
        }

        [HttpPost]
        public async Task<IActionResult> Create(CreateOrderRequest request)
        {
            var order = new Order { CustomerId = request.CustomerId, Total = request.Total };
            _db.Orders.Add(order);
            // Planted issue: Orders.Api also writes Invoices, which Billing.Core owns.
            _db.Invoices.Add(new Invoice { OrderId = order.Id, Amount = request.Total, Status = "Draft" });
            await _db.SaveChangesAsync();
            // Planted issue: direct publish after commit, contradicting ADR-0001 (outbox); no retry.
            await _publisher.PublishAsync("orders.created", new OrderCreated(order.Id));
            return Ok(order.Id);
        }
    }
}
