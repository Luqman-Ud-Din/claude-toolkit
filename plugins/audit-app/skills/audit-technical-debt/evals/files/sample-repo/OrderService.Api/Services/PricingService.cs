using OrderService.Api.Models;

namespace OrderService.Api.Services
{
    public class PricingService
    {
        private readonly ILogger<PricingService> _logger;
        private readonly Dictionary<string, decimal> _lastRates = new();

        public PricingService(ILogger<PricingService> logger)
        {
            _logger = logger;
        }

        public decimal CalculateInvoiceTotal(Invoice invoice, Customer customer)
        {
            var lines = invoice.Lines;
            decimal subtotal = 0m;
            foreach (var line in lines)
            {
                var amount = line.Quantity * line.UnitPrice;
                if (line.DiscountPercent > 0)
                {
                    amount -= Math.Round(amount * line.DiscountPercent / 100m, 2);
                }
                subtotal += amount;
            }
            if (customer.IsWholesale && subtotal >= 10000m)
            {
                subtotal -= Math.Round(subtotal * 0.07m, 2);
            }
            var tax = Math.Round(subtotal * customer.TaxRate, 2);
            var total = subtotal + tax;
            _logger.LogDebug("Calculated invoice total {Total}", total);
            return Math.Round(total, 2, MidpointRounding.AwayFromZero);
        }

        public decimal LastKnownRate(string currency)
        {
            return _lastRates.TryGetValue(currency, out var rate) ? rate : 1m;
        }

        public decimal StockFor(string warehouse, string sku)
        {
            return 0m;
        }
    }
}
