using Billing.Api.Services;
using Microsoft.AspNetCore.Mvc;

namespace Billing.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
public class InvoicesController : ControllerBase
{
    private readonly IInvoiceService _invoices;
    private readonly ReportCache _reports;

    public InvoicesController(IInvoiceService invoices, ReportCache reports)
    {
        _invoices = invoices;
        _reports = reports;
    }

    // OK: async action with CancellationToken - must NOT be flagged.
    [HttpPost("{id:int}/post")]
    public async Task<IActionResult> Post(int id, CancellationToken ct)
        => Ok(await _invoices.PostAsync(id, ct));

    // ASYNC (HTTP): HttpClient instantiated inside a request handler - socket exhaustion, no timeout.
    [HttpGet("{id:int}/pdf")]
    public async Task<IActionResult> Pdf(int id)
    {
        var client = new HttpClient();
        var bytes = await client.GetByteArrayAsync($"https://pdf.example/render?invoice={id}");
        return File(bytes, "application/pdf");
    }

    [HttpGet("outstanding")]
    public async Task<IActionResult> Outstanding(int companyId, CancellationToken ct)
        => Ok(await _reports.OutstandingAsync(companyId, ct));
}
