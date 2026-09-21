using System.Threading.Tasks;
using Ledger.Api.Users;
using Microsoft.EntityFrameworkCore;

namespace Ledger.Api.Stock
{
    public class StockLevel
    {
        public int Id { get; set; }
        public int ProductId { get; set; }
        public int Quantity { get; set; }
    }

    // Negative case: atomic conditional update. The availability check is inside
    // the UPDATE's WHERE, so two concurrent reservations cannot both succeed when
    // only one unit is left; 0 affected rows means insufficient stock.
    public class StockService
    {
        private readonly LedgerDbContext _db;

        public StockService(LedgerDbContext db)
        {
            _db = db;
        }

        public async Task<bool> TryReserveAsync(int productId, int qty)
        {
            var rows = await _db.Stock
                .Where(s => s.ProductId == productId && s.Quantity >= qty)
                .ExecuteUpdateAsync(s => s.SetProperty(x => x.Quantity, x => x.Quantity - qty));
            return rows == 1;
        }
    }
}
