using Billing.Api.Data;
using Microsoft.EntityFrameworkCore;

namespace Billing.Api.Services;

public interface IFbrClient { Task<string> SubmitAsync(Invoice invoice, CancellationToken ct); }

public class FbrClient : IFbrClient
{
    private readonly HttpClient _http;
    public FbrClient(HttpClient http) => _http = http;       // OK: typed client from IHttpClientFactory
    public async Task<string> SubmitAsync(Invoice invoice, CancellationToken ct)
    {
        using var response = await _http.PostAsJsonAsync("invoices", invoice, ct);
        response.EnsureSuccessStatusCode();
        return await response.Content.ReadAsStringAsync(ct);
    }
}

public interface IInvoiceService
{
    Task<Invoice> PostAsync(int id, CancellationToken ct);
    string PostSync(int id);
    void NotifyPosted(int id);
}

public class InvoiceService : IInvoiceService
{
    private readonly BillingDbContext _db;
    private readonly IFbrClient _fbr;
    private readonly ILogger<InvoiceService> _logger;

    public InvoiceService(BillingDbContext db, IFbrClient fbr, ILogger<InvoiceService> logger)
    {
        _db = db; _fbr = fbr; _logger = logger;
    }

    // OK: async all the way, token threaded through - must NOT be flagged.
    public async Task<Invoice> PostAsync(int id, CancellationToken ct)
    {
        var invoice = await _db.Invoices.FirstAsync(i => i.Id == id, ct);
        await _fbr.SubmitAsync(invoice, ct);
        invoice.Status = "Posted";
        await _db.SaveChangesAsync(ct);
        return invoice;
    }

    // ASYNC (BLOCK): synchronous block on async work - thread-pool starvation under load.
    public string PostSync(int id)
    {
        var invoice = _db.Invoices.FirstAsync(i => i.Id == id).Result;
        return _fbr.SubmitAsync(invoice, CancellationToken.None).GetAwaiter().GetResult();
    }

    // ASYNC (VOID): async void - exceptions from the SMS call are lost, caller cannot await.
    public async void NotifyPosted(int id)
    {
        var invoice = await _db.Invoices.FirstAsync(i => i.Id == id);
        await _fbr.SubmitAsync(invoice, CancellationToken.None);
        _logger.LogInformation("notified {Id}", id);
    }
}
