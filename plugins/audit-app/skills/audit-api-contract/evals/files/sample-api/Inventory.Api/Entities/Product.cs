namespace Inventory.Api.Entities;

public class Product
{
    public int Id { get; set; }
    public string Sku { get; set; } = "";
    public string Name { get; set; } = "";
    public decimal Price { get; set; }
    public decimal CostPrice { get; set; }
    public int CompanyId { get; set; }
    public bool IsDeleted { get; set; }
}
