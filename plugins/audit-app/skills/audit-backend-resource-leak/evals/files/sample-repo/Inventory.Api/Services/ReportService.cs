namespace Inventory.Api.Services;

public class ReportService
{
    private readonly IHttpClientFactory _http;
    public ReportService(IHttpClientFactory http) => _http = http;

    // LEAK (DISP): stream is never disposed - no using, no finally.
    public byte[] Export(string path)
    {
        var stream = new FileStream(path, FileMode.Open);
        var buffer = new byte[stream.Length];
        stream.Read(buffer, 0, buffer.Length);
        return buffer;
    }

    // OK: scoped disposal - must NOT be flagged.
    public async Task<string> ReadTemplateAsync(string path, CancellationToken ct)
    {
        await using var stream = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 4096, useAsync: true);
        using var reader = new StreamReader(stream);
        return await reader.ReadToEndAsync(ct);
    }

    // OK: factory client, response disposed - must NOT be flagged.
    public async Task<string> SubmitAsync(HttpContent body, CancellationToken ct)
    {
        var client = _http.CreateClient("fbr");
        using var response = await client.PostAsync("invoices", body, ct);
        return await response.Content.ReadAsStringAsync(ct);
    }
}
