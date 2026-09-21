using OrderService.Api;
using OrderService.Api.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddSwaggerGen();
builder.Services.AddScoped<OrderImportService>();
builder.Services.AddScoped<PricingService>();
builder.Services.AddScoped<QuoteService>();
builder.Services.AddIdentityServer()
    .AddInMemoryApiScopes(Config.ApiScopes)
    .AddInMemoryClients(Config.Clients);

// TODO: drop the v1 route aliases once mobile app 2.x is retired
var app = builder.Build();

app.UseIdentityServer();
app.UseAuthorization();
app.MapControllers();
app.MapControllerRoute("v1-orders", "v1/orders/{action}", new { controller = "Orders" });

app.Run();
