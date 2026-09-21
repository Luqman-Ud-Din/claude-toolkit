# Fixture: Shop.Api (.NET 8, EF Core)

Planted issues (each marked with an `ORM (...)` comment):
- `Controllers/ProductsController.cs` GetAll - whole table, tracked, no paging (UNBOUNDED + TRACKING).
- `Controllers/ProductsController.cs` Search - `Name.Contains(term)` with no index on Name (INDEX; cross-check with `Data/ShopDbContext.cs` HasIndex).
- `Managers/SaleManager.cs` CalculateTotalAsync - product query inside a foreach over sale lines (NPLUS1).
- `Managers/SaleManager.cs` HasSalesToday - `Count(...) > 0` (INEFFICIENT).
- `Managers/SaleManager.cs` PostAsync - two SaveChanges across Sales and StockMovements with no transaction (TXN).

Negatives that must NOT be flagged: `GetPage` (AsNoTracking + Skip/Take + Select projection), `Exists` (AnyAsync), `CalculateTotalBatchedAsync` (IN-batched lookup).
