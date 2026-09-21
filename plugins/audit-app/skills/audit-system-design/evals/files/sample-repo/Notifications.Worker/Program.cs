using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;

// Negative case: outbound SMS client has a timeout and the standard resilience handler; must NOT be flagged.
var builder = Host.CreateApplicationBuilder(args);
builder.Services.AddHttpClient("sms", c =>
{
    c.BaseAddress = new Uri(builder.Configuration["Sms:BaseUrl"] ?? "https://sms.example.invalid/");
    c.Timeout = TimeSpan.FromSeconds(10);
}).AddStandardResilienceHandler();
builder.Services.AddHostedService<Notifications.Worker.SmsConsumer>();
builder.Build().Run();
