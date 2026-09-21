using System.ComponentModel.DataAnnotations;

namespace Inventory.Api.Dtos;

public class PageQuery
{
    [Range(1, int.MaxValue)]
    public int Page { get; set; } = 1;

    [Range(1, 100)]
    public int PageSize { get; set; } = 20;
}

public record PagedResult<T>(IReadOnlyList<T> Items, int TotalCount, int Page, int PageSize);

public record UserSummaryDto(int Id, string Email, string DisplayName, string Role);
