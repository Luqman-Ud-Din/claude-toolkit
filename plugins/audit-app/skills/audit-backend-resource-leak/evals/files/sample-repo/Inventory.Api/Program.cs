using Inventory.Api.Services;
using Inventory.Api.Workers;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddMemoryCache();                       // LEAK: no SizeLimit (see ProductCache)
builder.Services.AddSingleton<RequestAudit>();
builder.Services.AddSingleton<ProductCache>();
builder.Services.AddScoped<ReportService>();
builder.Services.AddHttpClient("fbr", c => c.BaseAddress = new Uri("https://fbr.example/"));
builder.Services.AddHostedService<StockSyncWorker>();

var app = builder.Build();
app.MapControllers();
app.Run();
