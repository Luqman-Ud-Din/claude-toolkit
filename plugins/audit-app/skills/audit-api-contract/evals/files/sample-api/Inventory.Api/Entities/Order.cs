namespace Inventory.Api.Entities;

public enum OrderStatus { Pending, Paid, Cancelled }

public class Order
{
    public Guid Id { get; set; }
    public string Number { get; set; } = "";
    public decimal Total { get; set; }
    public OrderStatus Status { get; set; }
    public int CompanyId { get; set; }
    public int BranchId { get; set; }
    public DateTimeOffset CreatedAt { get; set; }
}
