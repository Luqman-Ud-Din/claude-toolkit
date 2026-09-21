namespace Inventory.Api.Data.Entities
{
    public class OrderLine
    {
        public int Id { get; set; }
        public int OrderId { get; set; }
        public Order Order { get; set; } = null!;

        // Planted issue: reference to Products with no navigation and no fluent relationship
        // -> EF creates neither a foreign key nor an index for this column.
        public int ProductId { get; set; }

        public int Qty { get; set; }

        // Planted issue: money stored in binary floating point.
        public double UnitPrice { get; set; }
        public double LineTotal { get; set; }

        // Planted issue: unbounded string (nvarchar(max)) for a short code.
        public string BatchCode { get; set; } = string.Empty;

        // Planted issue: naive DateTime (no offset) on an audit column.
        public DateTime CreatedAt { get; set; }
    }
}
