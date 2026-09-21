using Microsoft.AspNetCore.Authentication.JwtBearer;
using Shop.Api.Data;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddDbContext<ShopDbContext>();
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme).AddJwtBearer();
builder.Services.AddAuthorization();

var app = builder.Build();
app.UseAuthentication();
app.UseAuthorization();

// Minimal API: health probe is deliberately anonymous (negative: must NOT be flagged).
app.MapGet("/health", () => Results.Ok("ok")).AllowAnonymous();

// Minimal API with no RequireAuthorization and no global fallback policy.
app.MapGet("/api/export/orders", (ShopDbContext db) => db.Orders.ToList());

app.MapControllers();
app.Run();
