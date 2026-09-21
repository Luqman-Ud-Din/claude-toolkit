var builder = WebApplication.CreateBuilder(args);

// Planted: wildcard CORS combined with credentials - a browser can send another
// origin's cookies to this API. AllowAnyOrigin + AllowCredentials is invalid and
// dangerous; here the reflected-origin variant makes it effective.
builder.Services.AddCors(o => o.AddPolicy("open", p =>
    p.SetIsOriginAllowed(_ => true)   // reflects any Origin - effectively "*"
     .AllowAnyHeader()
     .AllowAnyMethod()
     .AllowCredentials()));

// Negative: a correctly scoped policy. Must NOT be flagged.
builder.Services.AddCors(o => o.AddPolicy("scoped", p =>
    p.WithOrigins("https://app.example.com")
     .AllowAnyHeader()
     .AllowCredentials()));

// Read the key from configuration/secret store (good) - but the value lives in
// appsettings.Production.json (bad); the finding is on the config file, not here.
var jwtKey = builder.Configuration["Jwt:Key"];

var app = builder.Build();

// Negative: developer exception page is guarded by the environment check.
if (app.Environment.IsDevelopment())
{
    app.UseDeveloperExceptionPage();
}

app.UseCors("open");
app.Run();
