using System.Text.Json;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using OrderService.Api.Models;
using OrderService.Api.Services;

namespace OrderService.Api.Controllers
{
    [Route("api/[controller]")]
    [ApiController]
    [Authorize]
    public class OrdersController : ControllerBase
    {
        private readonly OrderImportService _importService;
        private readonly PricingService _pricing;
        private readonly QuoteService _quotes;

        public OrdersController(OrderImportService importService, PricingService pricing, QuoteService quotes)
        {
            _importService = importService;
            _pricing = pricing;
            _quotes = quotes;
        }

        [HttpPost("import")]
        public ActionResult<ImportResult> Import([FromBody] List<OrderRow> rows, [FromQuery] bool dryRun = false)
        {
            var tenant = User.FindFirst("tenant")?.Value;
            if (tenant == null)
            {
                return Forbid();
            }
            var result = _importService.ImportOrders(rows, tenant, dryRun);
            return Ok(result);
        }

        [HttpPost("invoice-total")]
        public ActionResult<decimal> InvoiceTotal([FromBody] InvoiceRequest request)
        {
            return Ok(_pricing.CalculateInvoiceTotal(request.Invoice, request.Customer));
        }

        [HttpPost("quote-total")]
        public IActionResult QuoteTotal([FromBody] QuoteRequest request)
        {
            var total = _quotes.CalculateQuoteTotal(request.Quote, request.Customer);
            return Content(JsonSerializer.Serialize(new { total }), "application/json");
        }
    }
}
