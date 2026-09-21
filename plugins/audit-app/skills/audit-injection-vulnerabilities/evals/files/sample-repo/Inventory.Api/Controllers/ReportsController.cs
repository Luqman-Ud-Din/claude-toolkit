using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Inventory.Api.Data;
using Inventory.Api.Models;

namespace Inventory.Api.Controllers;

[Route("api/[controller]")]
[ApiController]
[Authorize]
public class ReportsController : ControllerBase
{
    private readonly InventoryDbContext _context;

    public ReportsController(InventoryDbContext context)
    {
        _context = context;
    }

    // ISSUE (planted): raw SQL string concatenation - SortColumn and SortDirection come
    // straight from the request body and are appended to the query text.
    [HttpPost("sales")]
    public async Task<IActionResult> GetSalesReport([FromBody] ReportRequest model)
    {
        var sql = "SELECT * FROM Sales WHERE BranchId = " + model.BranchId +
                  " ORDER BY " + model.SortColumn + " " + model.SortDirection;
        var rows = await _context.Sales.FromSqlRaw(sql).ToListAsync();
        return Ok(rows);
    }
}
