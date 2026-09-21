using Billing.Api.Data;
using Billing.Api.Services;

var builder = WebApplication.CreateBuilder(args);
builder.Services.AddControllers();
builder.Services.AddMemoryCache();
builder.Services.AddDbContext<BillingDbContext>(o => o.UseSqlServer(builder.Configuration.GetConnectionString("Billing")));

// ASYNC (DI): ReportCache is a singleton whose constructor takes the scoped BillingDbContext.
builder.Services.AddSingleton<ReportCache>();

// OK: scoped consumer of a scoped context, and a singleton that only takes singletons.
builder.Services.AddScoped<IInvoiceService, InvoiceService>();
builder.Services.AddSingleton<ITaxRateCache, TaxRateCache>();
builder.Services.AddHttpClient<IFbrClient, FbrClient>(c =>
{
    c.BaseAddress = new Uri(builder.Configuration["Fbr:Url"]!);
    c.Timeout = TimeSpan.FromSeconds(10);
});

var app = builder.Build();
app.MapControllers();
app.Run();
