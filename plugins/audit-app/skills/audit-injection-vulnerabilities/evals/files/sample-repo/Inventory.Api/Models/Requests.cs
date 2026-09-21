namespace Inventory.Api.Models;

public class ReportRequest
{
    public int BranchId { get; set; }
    public string SortColumn { get; set; } = "Date";
    public string SortDirection { get; set; } = "ASC";
}

public class ExportRequest
{
    public string FileName { get; set; } = string.Empty;
}

public class Product
{
    public int Id { get; set; }
    public string Sku { get; set; } = string.Empty;
    public int BranchId { get; set; }
    public int CompanyId { get; set; }
}

public class Sale
{
    public int Id { get; set; }
    public int BranchId { get; set; }
    public decimal Total { get; set; }
}
