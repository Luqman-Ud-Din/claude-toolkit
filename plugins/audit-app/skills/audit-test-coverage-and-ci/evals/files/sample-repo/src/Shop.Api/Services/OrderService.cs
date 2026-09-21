namespace Shop.Api.Services;

public record OrderLine(string Sku, int Quantity, decimal UnitPrice);

public record Order(Guid Id, int CompanyId, IReadOnlyList<OrderLine> Lines, decimal Total, string Status);

public interface IOrderRepository
{
    Task AddAsync(Order order, CancellationToken ct);
    Task<Order?> GetAsync(Guid id, int companyId, CancellationToken ct);
    Task UpdateAsync(Order order, CancellationToken ct);
}

public class OrderService
{
    private readonly IOrderRepository _orders;

    public OrderService(IOrderRepository orders) => _orders = orders;

    public async Task<Order> CreateAsync(int companyId, IReadOnlyList<OrderLine> lines, CancellationToken ct)
    {
        if (lines.Count == 0 || lines.Any(l => l.Quantity <= 0))
            throw new ArgumentException("An order needs at least one line with a positive quantity");
        var order = new Order(Guid.NewGuid(), companyId, lines, lines.Sum(l => l.Quantity * l.UnitPrice), "Pending");
        await _orders.AddAsync(order, ct);
        return order;
    }

    public async Task CancelAsync(Guid id, int companyId, CancellationToken ct)
    {
        var order = await _orders.GetAsync(id, companyId, ct) ?? throw new KeyNotFoundException();
        if (order.Status != "Pending")
            throw new InvalidOperationException("Only pending orders can be cancelled");
        await _orders.UpdateAsync(order with { Status = "Cancelled" }, ct);
    }
}
