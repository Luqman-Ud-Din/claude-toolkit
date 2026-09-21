namespace Shop.Api.Dto;

// Request shape for PUT /api/profile. Bound straight from the body.
public class UpdateProfileDto
{
    public string DisplayName { get; set; } = "";
    public string Email { get; set; } = "";
    public string Role { get; set; } = "";      // planted (c): caller can set their own role
    public bool IsAdmin { get; set; }           // planted (c): privilege flag exposed on a self-service DTO
}
