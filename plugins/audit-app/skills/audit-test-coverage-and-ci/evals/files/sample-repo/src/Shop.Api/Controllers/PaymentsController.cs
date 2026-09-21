using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Shop.Api.Services;

namespace Shop.Api.Controllers;

public record ChargeRequest(string CustomerRef, decimal Subtotal, decimal DiscountPercent, decimal TaxRate);

[ApiController]
[Authorize]
[Route("api/payments")]
public class PaymentsController : ControllerBase
{
    private readonly PaymentService _payments;

    public PaymentsController(PaymentService payments) => _payments = payments;

    [HttpPost("charge")]
    public async Task<ActionResult<ChargeResult>> Charge([FromBody] ChargeRequest request, CancellationToken ct)
        => Ok(await _payments.ChargeOrderAsync(request.CustomerRef, request.Subtotal, request.DiscountPercent,
            request.TaxRate, ct));
}
