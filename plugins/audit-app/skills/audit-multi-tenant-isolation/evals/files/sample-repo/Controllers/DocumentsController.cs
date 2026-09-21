using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Microsoft.Extensions.Caching.Distributed;
using Saas.Api.Data;
using Saas.Api.Infrastructure;

namespace Saas.Api.Controllers;

[ApiController]
[Route("api/[controller]")]
[Authorize]
public class DocumentsController : ControllerBase
{
    private readonly AppDbContext _db;
    private readonly IDistributedCache _cache;
    private readonly ITenantContext _tenant;
    public DocumentsController(AppDbContext db, IDistributedCache cache, ITenantContext tenant)
    { _db = db; _cache = cache; _tenant = tenant; }

    // Planted #4: cache key built from the record id alone - tenant A can be served tenant B's cached doc.
    [HttpGet("{id}")]
    public async Task<IActionResult> Get(int id)
    {
        var cacheKey = $"document:{id}";                 // no tenant segment in the key
        var cached = await _cache.GetStringAsync(cacheKey);
        if (cached is not null) return Ok(cached);
        var doc = _db.Documents.Find(id);
        if (doc is null) return NotFound();
        await _cache.SetStringAsync(cacheKey, doc.BlobPath);
        return Ok(doc.BlobPath);
    }

    // Planted #5: file download path has no tenant segment - guessable across tenants.
    [HttpGet("{id}/download")]
    public IActionResult Download(int id)
    {
        var path = $"/var/blobstore/documents/{id}.pdf"; // shared namespace, no tenant folder
        return PhysicalFile(path, "application/pdf");
    }

    // Negative: cache key and blob path both include the tenant id. Must NOT be flagged.
    [HttpGet("{id}/thumbnail")]
    public async Task<IActionResult> Thumbnail(int id)
    {
        var key = $"tenant:{_tenant.TenantId}:document:{id}:thumb";
        var cached = await _cache.GetStringAsync(key);
        var path = $"/var/blobstore/{_tenant.TenantId}/documents/{id}.png";
        return Ok(new { key, path, cached });
    }
}
