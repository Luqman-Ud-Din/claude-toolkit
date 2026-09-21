using System.Linq;
using System.Threading.Tasks;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace Ledger.Api.Users
{
    public class RegisterRequest
    {
        public string Email { get; set; } = "";
        public string Password { get; set; } = "";
    }

    public class User
    {
        public int Id { get; set; }
        public string Email { get; set; } = "";
        public string PasswordHash { get; set; } = "";
    }

    [Route("api/[controller]")]
    [ApiController]
    public class UsersController : ControllerBase
    {
        private readonly LedgerDbContext _db;

        public UsersController(LedgerDbContext db)
        {
            _db = db;
        }

        // ISSUE (check-then-act without a unique constraint): two concurrent
        // registrations with the same email both pass the Any() check and both
        // insert. migrations/001_init.sql has no unique index on Users.Email.
        [HttpPost("register")]
        public async Task<IActionResult> Register([FromBody] RegisterRequest request)
        {
            if (await _db.Users.AnyAsync(u => u.Email == request.Email))
            {
                return Conflict("Email already registered");
            }

            _db.Users.Add(new User { Email = request.Email, PasswordHash = Hash(request.Password) });
            await _db.SaveChangesAsync();
            return Ok();
        }

        private static string Hash(string s) => s; // placeholder
    }

    public class LedgerDbContext : DbContext
    {
        public DbSet<User> Users => Set<User>();
        public DbSet<Payments.Order> Orders => Set<Payments.Order>();
        public DbSet<Webhooks.WebhookEvent> WebhookEvents => Set<Webhooks.WebhookEvent>();
        public DbSet<Stock.StockLevel> Stock => Set<Stock.StockLevel>();

        protected override void OnModelCreating(ModelBuilder b)
        {
            // Negative case: WebhookEvents has a unique index on (Provider, EventId).
            b.Entity<Webhooks.WebhookEvent>().HasIndex(e => new { e.Provider, e.EventId }).IsUnique();
            // Note: no unique index on User.Email (the planted issue).
        }
    }
}
