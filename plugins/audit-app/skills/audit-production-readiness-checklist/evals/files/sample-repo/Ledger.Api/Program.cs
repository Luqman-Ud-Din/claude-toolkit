using Ledger.Api.Data;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddDbContext<LedgerDbContext>(o =>
{
    o.UseSqlServer(builder.Configuration.GetConnectionString("Default"));
    o.EnableSensitiveDataLogging();
});

// TODO: health endpoint - nothing registered anywhere in the solution yet.
builder.Services.AddSingleton(new HttpClient());   // no timeout, no resilience handler

var app = builder.Build();

app.UseDeveloperExceptionPage();   // not guarded by app.Environment.IsDevelopment()
app.UseSwaggerUI();

app.MapControllers();
app.Run();
