using System.Threading.Tasks;
using Ledger.Api.Users;
using Microsoft.AspNetCore.Mvc;

namespace Ledger.Api.Payments
{
    public enum OrderStatus { Pending, Paid, Cancelled }

    public class Order
    {
        public int Id { get; set; }
        public int CustomerId { get; set; }
        public decimal Total { get; set; }
        public OrderStatus Status { get; set; }
    }

    public class ChargeRequest
    {
        public int OrderId { get; set; }
    }

    public interface IPaymentGateway
    {
        Task<bool> ChargeAsync(int customerId, decimal amount);
    }

    [Route("api/[controller]")]
    [ApiController]
    public class PaymentsController : ControllerBase
    {
        private readonly LedgerDbContext _db;
        private readonly IPaymentGateway _gateway;

        public PaymentsController(LedgerDbContext db, IPaymentGateway gateway)
        {
            _db = db;
            _gateway = gateway;
        }

        // ISSUE (no idempotency key): nothing identifies a repeated request. A
        // double click or a client retry after a timeout charges the card twice.
        // The status check is in memory and the write is unconditional, so two
        // concurrent calls both see Pending and both charge.
        [HttpPost("charge")]
        public async Task<IActionResult> Charge([FromBody] ChargeRequest request)
        {
            var order = await _db.Orders.FindAsync(request.OrderId);
            if (order == null) return NotFound();
            if (order.Status != OrderStatus.Pending) return BadRequest("Order not payable");

            var ok = await _gateway.ChargeAsync(order.CustomerId, order.Total);
            if (!ok) return StatusCode(502, "Gateway declined");

            order.Status = OrderStatus.Paid;
            await _db.SaveChangesAsync();
            return Ok(new { order.Id, order.Status });
        }
    }
}
