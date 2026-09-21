using System;
using System.Linq;

namespace Shop.Api.Orders
{
    public interface ICouponRepository
    {
        Coupon? Find(string code);
    }

    public class PricingService
    {
        private readonly ICouponRepository _coupons;

        public PricingService(ICouponRepository coupons)
        {
            _coupons = coupons;
        }

        // Correct (negative case): subtotal is derived from line items every time.
        public decimal ComputeSubtotal(Order order)
        {
            return order.Lines.Sum(l => l.UnitPrice * l.Quantity);
        }

        // ISSUE (discount applied twice): the discount is subtracted from the
        // stored Total on every call and nothing checks whether
        // AppliedCouponCode is already set. OrdersController exposes this as
        // POST /orders/{id}/coupon, so sending the request twice (double click,
        // client retry) subtracts the coupon twice. SingleUse is never checked.
        public void ApplyCoupon(Order order, string code)
        {
            var coupon = _coupons.Find(code);
            if (coupon == null) throw new ArgumentException("Unknown coupon");
            order.Total -= coupon.Amount;
            order.AppliedCouponCode = code;
        }

        public void RecalculateTotal(Order order)
        {
            order.Subtotal = ComputeSubtotal(order);
            order.Total = order.Subtotal;
            if (order.AppliedCouponCode != null)
            {
                ApplyCoupon(order, order.AppliedCouponCode);   // second application path
            }
        }
    }
}
