namespace Shop.Api.Services;

public interface IPaymentGateway
{
    Task<string> ChargeAsync(string customerRef, decimal amount, string currency, CancellationToken ct);
    Task RefundAsync(string chargeId, decimal amount, CancellationToken ct);
}

public record ChargeResult(string ChargeId, decimal AmountCharged);

public class PaymentService
{
    private readonly IPaymentGateway _gateway;

    public PaymentService(IPaymentGateway gateway) => _gateway = gateway;

    public async Task<ChargeResult> ChargeOrderAsync(string customerRef, decimal subtotal, decimal discountPercent,
        decimal taxRate, CancellationToken ct)
    {
        if (discountPercent < 0 || discountPercent > 100)
            throw new ArgumentOutOfRangeException(nameof(discountPercent));

        var discounted = subtotal - subtotal * discountPercent / 100m;
        var total = Math.Round(discounted * (1 + taxRate), 2, MidpointRounding.AwayFromZero);
        var chargeId = await _gateway.ChargeAsync(customerRef, total, "USD", ct);
        return new ChargeResult(chargeId, total);
    }

    public Task RefundAsync(string chargeId, decimal amount, decimal alreadyRefunded, decimal charged, CancellationToken ct)
    {
        if (amount <= 0 || alreadyRefunded + amount > charged)
            throw new InvalidOperationException("Refund exceeds the charged amount");
        return _gateway.RefundAsync(chargeId, amount, ct);
    }
}
