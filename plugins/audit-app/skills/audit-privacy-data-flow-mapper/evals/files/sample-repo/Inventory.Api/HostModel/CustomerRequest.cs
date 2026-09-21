namespace Inventory.Api.HostModel
{
    public class CustomerRequest
    {
        public string FirstName { get; set; }
        public string LastName { get; set; }
        public string Email { get; set; }
        public string Phone { get; set; }
        public bool MarketingOptIn { get; set; }
    }
}
