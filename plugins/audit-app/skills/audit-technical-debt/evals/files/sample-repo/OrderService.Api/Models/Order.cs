namespace OrderService.Api.Models
{
    public enum SalesChannel { Web, PointOfSale, Wholesale, Marketplace, Phone, MobileApp }

    public enum OrderStatus { Pending, Paid, PartiallyPaid, Shipped, Delivered, Cancelled, OnHold, Returned, Refunded }

    public class Order
    {
        public string TenantCode { get; set; } = "";
        public int SourceLine { get; set; }
        public string OrderNumber { get; set; } = "";
        public string CustomerName { get; set; } = "";
        public DateTime OrderDate { get; set; }
        public SalesChannel Channel { get; set; }
        public OrderStatus Status { get; set; }
        public List<OrderLine> Lines { get; } = new();
        public decimal VolumeDiscount { get; set; }
        public decimal Tax { get; set; }
        public decimal Total { get; set; }
        public decimal FxRate { get; set; }
        public decimal TotalInBaseCurrency { get; set; }
        public bool RequiresApproval { get; set; }
    }

    public class OrderLine
    {
        public string Sku { get; set; } = "";
        public decimal Quantity { get; set; }
        public decimal UnitPrice { get; set; }
        public decimal Total { get; set; }
        public decimal Backordered { get; set; }
    }

    public class OrderRow
    {
        public string OrderNumber { get; set; } = "";
        public string CustomerCode { get; set; } = "";
        public string CustomerName { get; set; } = "";
        public string ShippingStreet { get; set; } = "";
        public string ShippingCity { get; set; } = "";
        public string ShippingCountry { get; set; } = "";
        public string Currency { get; set; } = "";
        public string OrderDate { get; set; } = "";
        public string Channel { get; set; } = "";
        public string SalesRep { get; set; } = "";
        public string? Status { get; set; }
        public string? Notes { get; set; }
        public string? PurchaseOrderRef { get; set; }
        public string? TaxExempt { get; set; }
        public string? TaxExemptionNumber { get; set; }
        public string? AllowBackorder { get; set; }
        public List<OrderRowLine>? Lines { get; set; }
    }

    public class OrderRowLine
    {
        public string Sku { get; set; } = "";
        public string Quantity { get; set; } = "";
        public string UnitPrice { get; set; } = "";
        public decimal? DiscountPercent { get; set; }
    }

    public class ImportResult
    {
        public List<string> Errors { get; } = new();
        public List<string> Warnings { get; } = new();
        public List<Order> Orders { get; } = new();
        public int Imported { get; set; }
        public int Validated { get; set; }
        public int WarningCount { get; set; }
    }

    public class FxRate
    {
        public decimal Value { get; set; }
    }

    public class PricedLine
    {
        public decimal Quantity { get; set; }
        public decimal UnitPrice { get; set; }
        public decimal DiscountPercent { get; set; }
    }

    public class Invoice
    {
        public List<PricedLine> Lines { get; } = new();
    }

    public class Quote
    {
        public List<PricedLine> Lines { get; } = new();
    }

    public class Customer
    {
        public bool IsWholesale { get; set; }
        public decimal TaxRate { get; set; }
    }

    public record InvoiceRequest(Invoice Invoice, Customer Customer);

    public record QuoteRequest(Quote Quote, Customer Customer);
}
