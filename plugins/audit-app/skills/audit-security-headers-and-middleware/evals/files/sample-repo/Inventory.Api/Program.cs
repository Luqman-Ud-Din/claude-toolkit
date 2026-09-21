using Microsoft.AspNetCore.Authentication.JwtBearer;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddCors(options =>
{
    options.AddPolicy("Frontend", policy =>
        policy.WithOrigins("https://app.sample-inventory.example.com")
              .AllowAnyHeader()
              .AllowAnyMethod()
              .AllowCredentials());
});
builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        options.Authority = builder.Configuration["Jwt:Authority"];
        options.Audience = builder.Configuration["Jwt:Audience"];
    });
builder.Services.AddAuthorization();

var app = builder.Build();

app.UseExceptionHandler("/error");
if (!app.Environment.IsDevelopment())
{
    app.UseHsts();
}
app.UseHttpsRedirection();

// ISSUE (planted): no CSP (and no X-Content-Type-Options / Referrer-Policy / Permissions-Policy).
// Only X-Frame-Options is emitted.
app.Use(async (context, next) =>
{
    context.Response.Headers["X-Frame-Options"] = "SAMEORIGIN";
    await next();
});

app.UseStaticFiles();
app.UseRouting();
app.UseCors("Frontend");

// ISSUE (planted): endpoints are mapped BEFORE authentication/authorization, so
// [Authorize] controllers run without the JWT being validated.
app.MapControllers();

app.UseAuthentication();
app.UseAuthorization();

app.Run();
