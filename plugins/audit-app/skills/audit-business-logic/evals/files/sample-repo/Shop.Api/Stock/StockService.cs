using System;

namespace Shop.Api.Stock
{
    // Negative case: correct stock handling. Decimal quantities, a negative
    // guard in the same unit of work, and every movement written to a ledger.
    // The guard-then-decrement still races under concurrency; that is
    // audit-concurrency-and-race-condition's finding, not a business-rule one.
    public class StockService
    {
        private readonly IStockRepository _repo;

        public StockService(IStockRepository repo)
        {
            _repo = repo;
        }

        public void Reserve(int productId, int branchId, decimal quantity, string reason)
        {
            if (quantity <= 0) throw new ArgumentOutOfRangeException(nameof(quantity));
            using var tx = _repo.BeginTransaction();
            var level = _repo.GetLevel(productId, branchId);
            if (level.Available < quantity)
                throw new InvalidOperationException("Insufficient stock");
            _repo.AddLedgerRow(productId, branchId, -quantity, reason);
            tx.Commit();
        }
    }

    public interface IStockRepository
    {
        IDisposableTransaction BeginTransaction();
        StockLevel GetLevel(int productId, int branchId);
        void AddLedgerRow(int productId, int branchId, decimal delta, string reason);
    }

    public interface IDisposableTransaction : IDisposable
    {
        void Commit();
    }

    public class StockLevel
    {
        public decimal OnHand { get; set; }
        public decimal Reserved { get; set; }
        public decimal Available => OnHand - Reserved;
    }
}
