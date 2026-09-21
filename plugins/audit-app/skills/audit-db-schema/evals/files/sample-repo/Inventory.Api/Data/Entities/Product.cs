using System.ComponentModel.DataAnnotations;

namespace Inventory.Api.Data.Entities
{
    // Negative case: this entity is correctly modelled and must NOT be flagged.
    public class Product
    {
        [Key]
        public int Id { get; set; }
        public int CompanyId { get; set; }
        [Required, MaxLength(64)]
        public string Sku { get; set; } = string.Empty;
        [Required, MaxLength(200)]
        public string Name { get; set; } = string.Empty;
        public decimal SalePrice { get; set; }
        public DateTimeOffset CreatedAt { get; set; }
        public int CreatedBy { get; set; }
        public DateTimeOffset? UpdatedAt { get; set; }
        public int? UpdatedBy { get; set; }
        public bool IsDeleted { get; set; }
        [Timestamp]
        public byte[] RowVersion { get; set; } = Array.Empty<byte>();
    }
}
