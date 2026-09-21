using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Saas.Api.Data;
using Saas.Api.Infrastructure;

namespace Saas.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class InvoicesController : ControllerBase
{
    private readonly AppDbContext _db;
    private readonly ITenantContext _tenant;
    public InvoicesController(AppDbContext db, ITenantContext tenant) { _db = db; _tenant = tenant; }

    // Negative: relies on the global query filter. Scoped to the caller's tenant. Must NOT be flagged.
    [HttpGet]
    public IActionResult List() => Ok(_db.Invoices.ToList());

    // Planted #1: raw SQL that bypasses the global query filter - returns every tenant's invoices.
    [HttpGet("report")]
    public IActionResult Report()
    {
        var all = _db.Invoices
            .FromSqlRaw("SELECT * FROM Invoices")   // no TenantId predicate, ignores HasQueryFilter
            .IgnoreQueryFilters()
            .ToList();
        return Ok(all);
    }

    // Planted #2: tenant id taken from the request body instead of the token claim.
    [HttpPost("create")]
    public IActionResult Create([FromBody] CreateInvoiceDto dto)
    {
        var inv = new Invoice { TenantId = dto.TenantId, Total = dto.Total, Number = dto.Number };
        _db.Invoices.Add(inv);
        _db.SaveChanges();
        return Ok(inv);
    }

    // Negative: write path sets TenantId from the resolved context. Must NOT be flagged.
    [HttpPost]
    public IActionResult CreateSafe([FromBody] CreateInvoiceDto dto)
    {
        var inv = new Invoice { TenantId = _tenant.TenantId, Total = dto.Total, Number = dto.Number };
        _db.Invoices.Add(inv);
        _db.SaveChanges();
        return Ok(inv);
    }
}

public class CreateInvoiceDto
{
    public int TenantId { get; set; }     // planted #2: client-controlled tenant id
    public decimal Total { get; set; }
    public string Number { get; set; } = "";
}
