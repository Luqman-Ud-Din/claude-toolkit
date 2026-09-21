namespace Inventory.Api.Workers;

public class StockSyncWorker : BackgroundService
{
    private readonly IServiceScopeFactory _scopes;
    private readonly ILogger<StockSyncWorker> _logger;
    private readonly List<int> _processed = new();     // grows across iterations, never cleared

    public StockSyncWorker(IServiceScopeFactory scopes, ILogger<StockSyncWorker> logger)
    {
        _scopes = scopes;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                using var scope = _scopes.CreateScope();
                var ids = await SyncOnceAsync(scope.ServiceProvider, stoppingToken);
                _processed.AddRange(ids);
            }
            catch (Exception) { }   // LEAK (BG): empty catch - failures never logged, worker loops silently
            await Task.Delay(TimeSpan.FromSeconds(30), stoppingToken);
        }
    }

    private static Task<int[]> SyncOnceAsync(IServiceProvider sp, CancellationToken ct)
        => Task.FromResult(new[] { 1, 2, 3 });
}
