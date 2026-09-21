using System.ComponentModel.DataAnnotations;

namespace Inventory.Api.Data.Entities
{
    // Negative case: password is hashed, email bounded and unique per company.
    public class User
    {
        [Key]
        public int Id { get; set; }
        public int CompanyId { get; set; }
        [Required, MaxLength(254)]
        public string Email { get; set; } = string.Empty;
        [Required, MaxLength(500)]
        public string PasswordHash { get; set; } = string.Empty;
        public DateTimeOffset CreatedAt { get; set; }
        public DateTimeOffset? UpdatedAt { get; set; }
        public bool IsDeleted { get; set; }
        [Timestamp]
        public byte[] RowVersion { get; set; } = Array.Empty<byte>();
    }
}
