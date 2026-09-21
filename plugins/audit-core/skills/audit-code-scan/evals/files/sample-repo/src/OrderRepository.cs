using Microsoft.EntityFrameworkCore;

public class OrderRepository
{
    private readonly ShopContext _db;
    public OrderRepository(ShopContext db) => _db = db;

    public List<Order> Search(string customer)
    {
        return _db.Orders.FromSqlRaw("SELECT * FROM Orders WHERE Customer = '" + customer + "'").ToList();
    }

    public List<Order> SearchSafe(string customer)
    {
        return _db.Orders.FromSqlInterpolated($"SELECT * FROM Orders WHERE Customer = {customer}").ToList();
    }
}
