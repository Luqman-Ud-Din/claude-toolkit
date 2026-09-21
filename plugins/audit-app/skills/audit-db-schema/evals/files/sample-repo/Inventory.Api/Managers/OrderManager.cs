using Microsoft.EntityFrameworkCore;
using Inventory.Api.Data;
using Inventory.Api.Data.Entities;

namespace Inventory.Api.Managers
{
    public class OrderManager
    {
        private readonly InventoryDbContext _db;
        public OrderManager(InventoryDbContext db) { _db = db; }

        // Justifying query for the missing OrderLines.ProductId index: stock report groups lines by product.
        public Task<List<OrderLine>> LinesForProduct(int companyId, int productId) =>
            _db.OrderLines.Where(l => l.ProductId == productId && l.Order.CompanyId == companyId).ToListAsync();

        // Main list page: filters by CompanyId/BranchId and sorts by CreatedAt (covered by IX on Orders).
        public Task<List<Order>> GetPaginationList(int companyId, int branchId, int page, int size) =>
            _db.Orders.Where(o => o.CompanyId == companyId && o.BranchId == branchId)
                      .OrderByDescending(o => o.CreatedAt).Skip(page * size).Take(size).ToListAsync();

        // Hard delete despite IsDeleted flag on Order.
        public async Task Delete(int id)
        {
            var order = await _db.Orders.FindAsync(id);
            if (order != null) { _db.Orders.Remove(order); await _db.SaveChangesAsync(); }
        }
    }
}
