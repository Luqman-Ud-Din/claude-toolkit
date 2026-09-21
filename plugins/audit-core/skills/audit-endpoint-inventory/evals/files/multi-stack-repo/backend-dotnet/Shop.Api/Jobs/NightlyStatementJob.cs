using Microsoft.EntityFrameworkCore;

namespace Shop.Api.Jobs;

public class NightlyStatementJob
{
    private readonly ShopDbContext _db;
    public NightlyStatementJob(ShopDbContext db) => _db = db;

    public void Run()
    {
        var accounts = _db.Accounts.ToList();
        foreach (var a in accounts) { a.StatementSent = true; }
        _db.SaveChanges();
    }
}
