using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Shop.Api.Orders
{
    public class ApplyCouponRequest
    {
        public string Code { get; set; } = "";
    }

    [Route("api/[controller]")]
    [ApiController]
    [Authorize]
    public class OrdersController : ControllerBase
    {
        private readonly OrderService _orders;
        private readonly PricingService _pricing;
        private readonly IOrderRepository _repo;

        public OrdersController(OrderService orders, PricingService pricing, IOrderRepository repo)
        {
            _orders = orders;
            _pricing = pricing;
            _repo = repo;
        }

        [HttpPost("{id}/pay")]
        public IActionResult Pay(int id)
        {
            _orders.Pay(id);          // reachable for Cancelled orders (see OrderService.Pay)
            return Ok();
        }

        [HttpPost("{id}/cancel")]
        public IActionResult Cancel(int id)
        {
            _orders.Cancel(id);
            return Ok();
        }

        [HttpPost("{id}/coupon")]
        public IActionResult ApplyCoupon(int id, [FromBody] ApplyCouponRequest request)
        {
            var order = _repo.Get(id);
            _pricing.ApplyCoupon(order, request.Code);   // no guard against a second call
            _repo.Save(order);
            return Ok(order.Total);
        }

        [HttpPut("{id}/lines")]
        public IActionResult UpdateLines(int id, [FromBody] OrderLine[] lines)
        {
            var order = _repo.Get(id);
            order.Lines = lines.ToList();
            _pricing.RecalculateTotal(order);
            _repo.Save(order);
            return Ok(order.Total);
        }
    }
}
