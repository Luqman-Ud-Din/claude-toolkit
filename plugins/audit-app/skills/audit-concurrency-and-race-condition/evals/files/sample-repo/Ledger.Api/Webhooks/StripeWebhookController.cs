using System;
using System.Threading.Tasks;
using Ledger.Api.Users;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace Ledger.Api.Webhooks
{
    public class WebhookEvent
    {
        public int Id { get; set; }
        public string Provider { get; set; } = "";
        public string EventId { get; set; } = "";
        public DateTimeOffset ReceivedAt { get; set; }
    }

    // Negative case: idempotent webhook. The provider event id is inserted first
    // under a unique index (Provider, EventId); a replay fails the insert and is
    // acknowledged without processing again.
    [Route("api/webhooks/stripe")]
    [ApiController]
    [AllowAnonymous]
    public class StripeWebhookController : ControllerBase
    {
        private readonly LedgerDbContext _db;

        public StripeWebhookController(LedgerDbContext db)
        {
            _db = db;
        }

        [HttpPost]
        public async Task<IActionResult> Receive([FromHeader(Name = "Stripe-Signature")] string signature, [FromBody] StripeEvent evt)
        {
            if (!SignatureValid(signature)) return Unauthorized();

            _db.WebhookEvents.Add(new WebhookEvent { Provider = "stripe", EventId = evt.Id, ReceivedAt = DateTimeOffset.UtcNow });
            try
            {
                await _db.SaveChangesAsync();
            }
            catch (DbUpdateException)
            {
                return Ok("duplicate ignored");   // unique index hit: already processed
            }

            await ProcessAsync(evt);
            return Ok();
        }

        private static bool SignatureValid(string s) => !string.IsNullOrEmpty(s);
        private Task ProcessAsync(StripeEvent e) => Task.CompletedTask;
    }

    public class StripeEvent
    {
        public string Id { get; set; } = "";
        public string Type { get; set; } = "";
    }
}
