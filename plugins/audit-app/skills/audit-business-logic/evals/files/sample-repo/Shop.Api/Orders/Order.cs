using System;
using System.Collections.Generic;

namespace Shop.Api.Orders
{
    public enum OrderStatus
    {
        Pending,
        Paid,
        Shipped,
        Completed,
        Cancelled,
        Refunded
    }

    public class OrderLine
    {
        public int ProductId { get; set; }
        public int Quantity { get; set; }
        public decimal UnitPrice { get; set; }
        // Weight is a physical measure, not money: double is acceptable here (negative case).
        public double WeightKg { get; set; }
    }

    public class Order
    {
        public int Id { get; set; }
        public int CustomerId { get; set; }
        public OrderStatus Status { get; set; }
        public List<OrderLine> Lines { get; set; } = new();
        public decimal Subtotal { get; set; }
        public decimal Total { get; set; }
        public string? AppliedCouponCode { get; set; }
        public DateTime CreatedUtc { get; set; }
    }

    public class Coupon
    {
        public string Code { get; set; } = "";
        public decimal Amount { get; set; }
        public bool SingleUse { get; set; }
    }
}
