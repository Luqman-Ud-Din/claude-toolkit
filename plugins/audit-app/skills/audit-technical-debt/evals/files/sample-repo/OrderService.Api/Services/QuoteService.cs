using OrderService.Api.Models;

namespace OrderService.Api.Services
{
    public class QuoteService
    {
        private readonly ILogger<QuoteService> _logger;

        public QuoteService(ILogger<QuoteService> logger)
        {
            _logger = logger;
        }

        public decimal CalculateQuoteTotal(Quote quote, Customer customer)
        {
            var lines = quote.Lines;
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
            // var legacyDiscount = subtotal * 0.05m;
            // if (customer.IsLegacy)
            // {
            //     subtotal -= legacyDiscount;
            // }
            var tax = Math.Round(subtotal * customer.TaxRate, 2);
            var total = subtotal + tax;
            _logger.LogDebug("Calculated quote total {Total}", total);
            return Math.Round(total, 2, MidpointRounding.AwayFromZero);
        }
    }
}
