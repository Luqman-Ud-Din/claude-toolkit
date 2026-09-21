public class ModelClient
{
    private readonly HttpClient _http;

    public ModelClient(HttpClient http) => _http = http;

    // No SDK - hand-rolled HTTP call straight to the provider's REST endpoint.
    public async Task<string> CompleteAsync(string prompt)
    {
        var response = await _http.PostAsJsonAsync("https://api.example-model-provider.com/v1/complete",
            new { prompt });
        return await response.Content.ReadAsStringAsync();
    }
}
