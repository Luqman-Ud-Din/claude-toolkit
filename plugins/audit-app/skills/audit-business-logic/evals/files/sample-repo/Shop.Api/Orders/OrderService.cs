using System;
using System.Linq;

namespace Shop.Api.Orders
{
    public interface IOrderRepository
    {
        Order Get(int id);
        void Save(Order order);
    }

    public interface IPaymentGateway
    {
        bool Charge(int customerId, double amount);
    }

    public class OrderService
    {
        private readonly IOrderRepository _repo;
        private readonly IPaymentGateway _gateway;

        public OrderService(IOrderRepository repo, IPaymentGateway gateway)
        {
            _repo = repo;
            _gateway = gateway;
        }

        // ISSUE (state machine): no check of the current status. A Cancelled
        // (or already Paid, or Refunded) order can be moved to Paid.
        public void Pay(int orderId)
        {
            var order = _repo.Get(orderId);
            double amountToCharge = (double)order.Total;      // ISSUE: money arithmetic on double
            if (_gateway.Charge(order.CustomerId, amountToCharge))
            {
                order.Status = OrderStatus.Paid;
                _repo.Save(order);
            }
        }

        public void Cancel(int orderId)
        {
            var order = _repo.Get(orderId);
            switch (order.Status)
            {
                case OrderStatus.Pending:
                case OrderStatus.Paid:
                    order.Status = OrderStatus.Cancelled;
                    break;
                case OrderStatus.Shipped:
                    throw new InvalidOperationException("Shipped orders cannot be cancelled; request a return.");
                default:
                    throw new InvalidOperationException($"Cannot cancel an order in status {order.Status}.");
            }
            _repo.Save(order);
        }

        // Correct guard (negative case): only Paid orders can ship.
        public void Ship(int orderId)
        {
            var order = _repo.Get(orderId);
            if (order.Status != OrderStatus.Paid)
                throw new InvalidOperationException($"Only paid orders can be shipped (current: {order.Status}).");
            order.Status = OrderStatus.Shipped;
            _repo.Save(order);
        }
    }
}
