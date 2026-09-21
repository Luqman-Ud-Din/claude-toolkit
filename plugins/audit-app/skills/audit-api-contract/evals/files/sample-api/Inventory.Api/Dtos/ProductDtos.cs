namespace Inventory.Api.Dtos;

public record ProductDto(int Id, string Sku, string Name, decimal Price);

public class CreateProductRequest
{
    public string Sku { get; set; } = "";
    public string Name { get; set; } = "";
    public decimal Price { get; set; }
    public decimal CostPrice { get; set; }
}
