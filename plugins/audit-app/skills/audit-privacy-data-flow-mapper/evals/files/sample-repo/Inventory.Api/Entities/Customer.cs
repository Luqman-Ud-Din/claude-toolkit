using System;

namespace Inventory.Api.Entities
{
    public class Customer
    {
        public int Id { get; set; }
        public int CompanyId { get; set; }
        public string FirstName { get; set; }
        public string LastName { get; set; }
        public string Email { get; set; }
        public string Phone { get; set; }
        public DateTime? DateOfBirth { get; set; }
        public bool MarketingOptIn { get; set; }
        public DateTime CreatedAt { get; set; }
    }
}
