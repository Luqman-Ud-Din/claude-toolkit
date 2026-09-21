using System.Diagnostics;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;
using Inventory.Api.Models;

namespace Inventory.Api.Controllers;

[Route("api/[controller]")]
[ApiController]
[Authorize]
public class ExportController : ControllerBase
{
    private readonly string _exportRoot = "C:\\inventory\\exports";

    // ISSUE (planted): OS command built from user input - model.FileName is interpolated
    // into a cmd.exe /c command line, so "x.pdf & whoami" runs whoami on the server.
    [HttpPost("convert")]
    public IActionResult ConvertToPdf([FromBody] ExportRequest model)
    {
        var psi = new ProcessStartInfo
        {
            FileName = "cmd.exe",
            Arguments = "/c convert " + _exportRoot + "\\" + model.FileName + " " + _exportRoot + "\\out.pdf",
            UseShellExecute = false,
            RedirectStandardOutput = true
        };
        using var process = Process.Start(psi);
        process!.WaitForExit();
        return Ok(new { converted = true });
    }
}
