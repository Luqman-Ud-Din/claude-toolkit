using Hangfire;
using Shop.Api.Jobs;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddAuthentication().AddJwtBearer();
builder.Services.AddAuthorization();
builder.Services.AddHangfire(c => c.UseInMemoryStorage());

var app = builder.Build();
app.UseAuthentication();
app.UseAuthorization();

// Planted: anonymous minimal API.
app.MapGet("/api/health", () => Results.Ok("ok")).AllowAnonymous();

// Minimal API: tenant id in the route, policy-protected.
app.MapGet("/api/tenants/{tenantId:int}/usage", (int tenantId, ShopDbContext db) =>
    db.Usage.Where(u => u.TenantId == tenantId).ToList())
    .RequireAuthorization("TenantAdmin");

// Planted: Hangfire recurring job.
RecurringJob.AddOrUpdate<NightlyStatementJob>("nightly-statements", job => job.Run(), Cron.Daily);

app.MapControllers();
app.Run();
