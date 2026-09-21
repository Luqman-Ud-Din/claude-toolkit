// build output copy: must never be scanned
public class Leftover { void X(ShopContext db, string s) { db.Orders.FromSqlRaw("SELECT * FROM Orders WHERE Id = " + s); } }
