using IdentityServer4.Models;

namespace OrderService.Api
{
    public static class Config
    {
        public static IEnumerable<ApiScope> ApiScopes => new[]
        {
            new ApiScope("orders.api", "Orders API")
        };

        public static IEnumerable<Client> Clients => new[]
        {
            new Client
            {
                ClientId = "mobile-app",
                AllowedGrantTypes = GrantTypes.ClientCredentials,
                ClientSecrets = { new Secret("from-key-vault".Sha256()) },
                AllowedScopes = { "orders.api" }
            }
        };
    }
}
