namespace Shop.Api.Dto;

// Negative: a request DTO with only business fields. Must NOT be flagged.
public class CreateOrderDto
{
    public decimal Total { get; set; }
    public string Note { get; set; } = "";
}
