using System.ComponentModel.DataAnnotations;
using Inventory.Api.Entities;

namespace Inventory.Api.Dtos;

public record OrderDto(Guid Id, string Number, decimal Total, OrderStatus Status, DateTimeOffset CreatedAt);

public class CreateOrderRequest
{
    [Required]
    [Range(1, int.MaxValue)]
    public int BranchId { get; set; }

    [Required]
    [MinLength(1)]
    public List<OrderLineRequest> Lines { get; set; } = new();

    [StringLength(32)]
    public string? CouponCode { get; set; }
}

public class OrderLineRequest
{
    [Required]
    [StringLength(64)]
    public string Sku { get; set; } = "";

    [Range(1, 10_000)]
    public int Quantity { get; set; }
}
