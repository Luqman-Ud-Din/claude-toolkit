using System.Net.Http.Json;
using Inventory.Api.Entities;
using Inventory.Api.HostModel;
using Microsoft.Extensions.Caching.Distributed;
using Microsoft.Extensions.Logging;

namespace Inventory.Api.Services
{
    public class CustomerService
    {
        private readonly AppDbContext _db;
        private readonly IDistributedCache _cache;
        private readonly HttpClient _http;
        private readonly ILogger<CustomerService> _logger;

        public CustomerService(AppDbContext db, IDistributedCache cache, HttpClient http, ILogger<CustomerService> logger)
        {
            _db = db; _cache = cache; _http = http; _logger = logger;
        }

        public async Task<int> RegisterAsync(CustomerRequest request)
        {
            var customer = new Customer
            {
                FirstName = request.FirstName,
                LastName = request.LastName,
                Email = request.Email,
                Phone = request.Phone,
                MarketingOptIn = request.MarketingOptIn,
                CreatedAt = DateTime.UtcNow
            };
            _db.Customers.Add(customer);
            await _db.SaveChangesAsync();

            _logger.LogInformation("Customer {Email} registered for company {CompanyId}", customer.Email, customer.CompanyId);

            await _cache.SetStringAsync($"customer:{customer.Email}", customer.Id.ToString());

            var payload = new { email_address = customer.Email, status = "subscribed",
                                merge_fields = new { FNAME = customer.FirstName, LNAME = customer.LastName } };
            await _http.PostAsJsonAsync("https://us1.api.mailchimp.com/3.0/lists/4f1c2a/members", payload);

            _logger.LogInformation("Customer {CustomerId} synced to marketing list", customer.Id);
            return customer.Id;
        }

        public async Task<Customer?> GetAsync(int id)
        {
            var cached = await _cache.GetStringAsync($"customer:id:{id}");
            return await _db.Customers.FindAsync(id);
        }
    }
}
