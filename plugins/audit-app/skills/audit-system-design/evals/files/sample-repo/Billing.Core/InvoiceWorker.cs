using Microsoft.EntityFrameworkCore;
using Orders.Api.Data;

namespace Billing.Core
{
    public class BillingDbContext : DbContext
    {
        public BillingDbContext(DbContextOptions<BillingDbContext> o) : base(o) { }
        public DbSet<Invoice> Invoices { get; set; }
    }

    // Consumes orders.created and finalises invoices. Second writer of the Invoices table.
    public class InvoiceWorker : BackgroundService
    {
        private readonly BillingDbContext _db;
        public InvoiceWorker(BillingDbContext db) { _db = db; }

        protected override async Task ExecuteAsync(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                var draft = await _db.Invoices.FirstOrDefaultAsync(i => i.Status == "Draft", ct);
                if (draft != null)
                {
                    draft.Status = "Issued";
                    _db.Invoices.Update(draft);
                    await _db.SaveChangesAsync(ct);
                }
                await Task.Delay(5000, ct);
            }
        }
    }
}
