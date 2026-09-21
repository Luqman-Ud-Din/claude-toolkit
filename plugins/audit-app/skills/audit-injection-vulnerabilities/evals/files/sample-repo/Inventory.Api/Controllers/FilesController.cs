using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace Inventory.Api.Controllers;

[Route("api/[controller]")]
[ApiController]
[Authorize]
public class FilesController : ControllerBase
{
    private readonly string _root = "C:\\inventory\\attachments";

    // ISSUE (planted): path traversal - "name" is a route parameter joined onto the root
    // with no GetFileName / prefix check. ../../appsettings.json reads the config file.
    [HttpGet("download/{name}")]
    public IActionResult Download(string name)
    {
        var fullPath = Path.Combine(_root, name);
        if (!System.IO.File.Exists(fullPath))
        {
            return NotFound();
        }
        var bytes = System.IO.File.ReadAllBytes(fullPath);
        return File(bytes, "application/octet-stream", name);
    }
}
