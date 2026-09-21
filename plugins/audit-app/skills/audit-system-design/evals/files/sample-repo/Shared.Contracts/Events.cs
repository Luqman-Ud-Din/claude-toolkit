namespace Shared.Contracts
{
    // Negative case: a leaf contracts library with high fan-in and no dependencies is expected.
    public record OrderCreated(int OrderId);
    public record CreateOrderRequest(int CustomerId, decimal Total);

    public interface IEventPublisher
    {
        Task PublishAsync(string routingKey, object payload);
    }
}
