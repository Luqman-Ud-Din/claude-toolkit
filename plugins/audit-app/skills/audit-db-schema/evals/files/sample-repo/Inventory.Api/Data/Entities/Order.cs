using System.ComponentModel.DataAnnotations;

namespace Inventory.Api.Data.Entities
{
    public class Order
    {
        [Key]
        public int Id { get; set; }
        public int CompanyId { get; set; }
        public int BranchId { get; set; }
        [MaxLength(32)]
        public string OrderNo { get; set; } = string.Empty;
        public decimal Total { get; set; }
        public DateTimeOffset CreatedAt { get; set; }
        public int CreatedBy { get; set; }
        public DateTimeOffset? UpdatedAt { get; set; }
        public bool IsDeleted { get; set; }
        [Timestamp]
        public byte[] RowVersion { get; set; } = Array.Empty<byte>();
        public ICollection<OrderLine> Lines { get; set; } = new List<OrderLine>();
    }
}
