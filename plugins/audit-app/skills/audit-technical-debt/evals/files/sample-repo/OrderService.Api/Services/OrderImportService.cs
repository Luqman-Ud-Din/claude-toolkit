using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Net;
using Newtonsoft.Json;
using OrderService.Api.Models;

namespace OrderService.Api.Services
{
    public class OrderImportService
    {
        private readonly PricingService _pricing;
        private readonly ILogger<OrderImportService> _logger;

        public OrderImportService(PricingService pricing, ILogger<OrderImportService> logger)
        {
            _pricing = pricing;
            _logger = logger;
        }

        public ImportResult ImportOrders(IReadOnlyList<OrderRow> rows, string tenantCode, bool dryRun)
        {
            var result = new ImportResult();
            var lineNo = 0;
            var warnings = 0;
            var seenOrderNumbers = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
            if (rows == null || rows.Count == 0)
            {
                result.Errors.Add("File contains no rows");
                return result;
            }
            if (string.IsNullOrWhiteSpace(tenantCode))
            {
                throw new ArgumentException("Tenant code is required", nameof(tenantCode));
            }
            // TODO: move the region tax table into configuration
            foreach (var row in rows)
            {
                lineNo++;
                var order = new Order { TenantCode = tenantCode, SourceLine = lineNo };
                if (string.IsNullOrWhiteSpace(row.OrderNumber))
                {
                    result.Errors.Add($"Row {lineNo}: OrderNumber is required");
                    continue;
                }
                if (string.IsNullOrWhiteSpace(row.CustomerCode))
                {
                    result.Errors.Add($"Row {lineNo}: CustomerCode is required");
                    continue;
                }
                if (string.IsNullOrWhiteSpace(row.CustomerName))
                {
                    result.Errors.Add($"Row {lineNo}: CustomerName is required");
                    continue;
                }
                if (string.IsNullOrWhiteSpace(row.ShippingStreet))
                {
                    result.Errors.Add($"Row {lineNo}: ShippingStreet is required");
                    continue;
                }
                if (string.IsNullOrWhiteSpace(row.ShippingCity))
                {
                    result.Errors.Add($"Row {lineNo}: ShippingCity is required");
                    continue;
                }
                if (string.IsNullOrWhiteSpace(row.ShippingCountry))
                {
                    result.Errors.Add($"Row {lineNo}: ShippingCountry is required");
                    continue;
                }
                if (string.IsNullOrWhiteSpace(row.Currency))
                {
                    result.Errors.Add($"Row {lineNo}: Currency is required");
                    continue;
                }
                if (string.IsNullOrWhiteSpace(row.OrderDate))
                {
                    result.Errors.Add($"Row {lineNo}: OrderDate is required");
                    continue;
                }
                if (string.IsNullOrWhiteSpace(row.Channel))
                {
                    result.Errors.Add($"Row {lineNo}: Channel is required");
                    continue;
                }
                if (string.IsNullOrWhiteSpace(row.SalesRep))
                {
                    result.Errors.Add($"Row {lineNo}: SalesRep is required");
                    continue;
                }
                if (row.CustomerName != null && row.CustomerName.Length > 120)
                {
                    row.CustomerName = row.CustomerName.Substring(0, 120);
                    warnings++;
                }
                if (row.ShippingStreet != null && row.ShippingStreet.Length > 200)
                {
                    row.ShippingStreet = row.ShippingStreet.Substring(0, 200);
                    warnings++;
                }
                if (row.ShippingCity != null && row.ShippingCity.Length > 80)
                {
                    row.ShippingCity = row.ShippingCity.Substring(0, 80);
                    warnings++;
                }
                if (row.Notes != null && row.Notes.Length > 500)
                {
                    row.Notes = row.Notes.Substring(0, 500);
                    warnings++;
                }
                if (row.SalesRep != null && row.SalesRep.Length > 60)
                {
                    row.SalesRep = row.SalesRep.Substring(0, 60);
                    warnings++;
                }
                if (row.PurchaseOrderRef != null && row.PurchaseOrderRef.Length > 40)
                {
                    row.PurchaseOrderRef = row.PurchaseOrderRef.Substring(0, 40);
                    warnings++;
                }
                if (row.CustomerCode != null && row.CustomerCode.Length > 20)
                {
                    row.CustomerCode = row.CustomerCode.Substring(0, 20);
                    warnings++;
                }
                if (row.OrderNumber != null && row.OrderNumber.Length > 30)
                {
                    row.OrderNumber = row.OrderNumber.Substring(0, 30);
                    warnings++;
                }
                if (!seenOrderNumbers.Add(row.OrderNumber))
                {
                    result.Errors.Add($"Row {lineNo}: duplicate order number {row.OrderNumber}");
                    continue;
                }
                if (!DateTime.TryParseExact(row.OrderDate, "yyyy-MM-dd", CultureInfo.InvariantCulture, DateTimeStyles.None, out var orderDate))
                {
                    result.Errors.Add($"Row {lineNo}: bad order date");
                    continue;
                }
                order.OrderDate = orderDate;
                switch (row.Channel.Trim().ToUpperInvariant())
                {
                    case "WEB":
                        order.Channel = SalesChannel.Web;
                        break;
                    case "POS":
                        order.Channel = SalesChannel.PointOfSale;
                        break;
                    case "B2B":
                        order.Channel = SalesChannel.Wholesale;
                        break;
                    case "MKT":
                        order.Channel = SalesChannel.Marketplace;
                        break;
                    case "TEL":
                        order.Channel = SalesChannel.Phone;
                        break;
                    case "APP":
                        order.Channel = SalesChannel.MobileApp;
                        break;
                    default:
                        result.Errors.Add($"Row {lineNo}: unknown channel {row.Channel}");
                        continue;
                }
                switch (row.Status?.Trim().ToUpperInvariant())
                {
                    case "NEW":
                        order.Status = OrderStatus.Pending;
                        break;
                    case "OPEN":
                        order.Status = OrderStatus.Pending;
                        break;
                    case "PAID":
                        order.Status = OrderStatus.Paid;
                        break;
                    case "PART":
                        order.Status = OrderStatus.PartiallyPaid;
                        break;
                    case "SHIP":
                        order.Status = OrderStatus.Shipped;
                        break;
                    case "DELV":
                        order.Status = OrderStatus.Delivered;
                        break;
                    case "CANC":
                        order.Status = OrderStatus.Cancelled;
                        break;
                    case "HOLD":
                        order.Status = OrderStatus.OnHold;
                        break;
                    case "RET":
                        order.Status = OrderStatus.Returned;
                        break;
                    case "REF":
                        order.Status = OrderStatus.Refunded;
                        break;
                    default:
                        order.Status = OrderStatus.Pending;
                        warnings++;
                        break;
                }
                if (order.Status == OrderStatus.Cancelled && !dryRun)
                {
                    _logger.LogInformation("Skipping cancelled order {OrderNumber}", row.OrderNumber);
                    continue;
                }
                decimal subtotal = 0m;
                var lineItems = row.Lines ?? new List<OrderRowLine>();
                if (lineItems.Count == 0)
                {
                    result.Errors.Add($"Row {lineNo}: order has no lines");
                    continue;
                }
                foreach (var line in lineItems)
                {
                    if (string.IsNullOrWhiteSpace(line.Sku))
                    {
                        result.Errors.Add($"Row {lineNo}: line without SKU");
                        continue;
                    }
                    if (!decimal.TryParse(line.Quantity, NumberStyles.Number, CultureInfo.InvariantCulture, out var qty) || qty <= 0)
                    {
                        result.Errors.Add($"Row {lineNo}: invalid quantity for {line.Sku}");
                        continue;
                    }
                    if (!decimal.TryParse(line.UnitPrice, NumberStyles.Number, CultureInfo.InvariantCulture, out var price) || price < 0)
                    {
                        result.Errors.Add($"Row {lineNo}: invalid price for {line.Sku}");
                        continue;
                    }
                    if (line.Sku.StartsWith("SVC-") && qty != Math.Floor(qty))
                    {
                        qty = Math.Ceiling(qty);
                        warnings++;
                    }
                    var lineTotal = qty * price;
                    if (line.DiscountPercent != null && line.DiscountPercent > 0 && line.DiscountPercent <= 100)
                    {
                        lineTotal -= Math.Round(lineTotal * line.DiscountPercent.Value / 100m, 2);
                    }
                    else if (line.DiscountPercent > 100)
                    {
                        result.Errors.Add($"Row {lineNo}: discount over 100% on {line.Sku}");
                        continue;
                    }
                    order.Lines.Add(new OrderLine { Sku = line.Sku, Quantity = qty, UnitPrice = price, Total = lineTotal });
                    subtotal += lineTotal;
                }
                if (order.Lines.Count == 0)
                {
                    continue;
                }
                if (subtotal >= 50000m && order.Channel == SalesChannel.Wholesale)
                {
                    order.VolumeDiscount = Math.Round(subtotal * 12m / 100m, 2);
                }
                else if (subtotal >= 25000m && order.Channel == SalesChannel.Wholesale)
                {
                    order.VolumeDiscount = Math.Round(subtotal * 9m / 100m, 2);
                }
                else if (subtotal >= 10000m && order.Channel == SalesChannel.Wholesale)
                {
                    order.VolumeDiscount = Math.Round(subtotal * 7m / 100m, 2);
                }
                else if (subtotal >= 5000m && order.Channel == SalesChannel.Wholesale)
                {
                    order.VolumeDiscount = Math.Round(subtotal * 5m / 100m, 2);
                }
                else if (subtotal >= 2500m && order.Channel == SalesChannel.Wholesale)
                {
                    order.VolumeDiscount = Math.Round(subtotal * 3m / 100m, 2);
                }
                else if (subtotal >= 1000m && order.Channel == SalesChannel.Wholesale)
                {
                    order.VolumeDiscount = Math.Round(subtotal * 2m / 100m, 2);
                }
                else if (subtotal >= 1000m && row.CustomerCode.StartsWith("VIP"))
                {
                    order.VolumeDiscount = Math.Round(subtotal * 0.04m, 2);
                }
                else
                {
                    order.VolumeDiscount = 0m;
                }
                decimal taxRate;
                switch (row.ShippingCountry.Trim().ToUpperInvariant())
                {
                    case "PK":
                        taxRate = 0.18m;
                        break;
                    case "AE":
                        taxRate = 0.05m;
                        break;
                    case "SA":
                        taxRate = 0.15m;
                        break;
                    case "GB":
                        taxRate = 0.20m;
                        break;
                    case "DE":
                        taxRate = 0.19m;
                        break;
                    case "FR":
                        taxRate = 0.20m;
                        break;
                    case "NL":
                        taxRate = 0.21m;
                        break;
                    case "US":
                        taxRate = 0m;
                        break;
                    case "CA":
                        taxRate = 0.05m;
                        break;
                    case "AU":
                        taxRate = 0.10m;
                        break;
                    default:
                        taxRate = 0m;
                        result.Warnings.Add($"Row {lineNo}: no tax rule for {row.ShippingCountry}");
                        break;
                }
                if (row.TaxExempt == "Y" && !string.IsNullOrWhiteSpace(row.TaxExemptionNumber))
                {
                    taxRate = 0m;
                }
                else if (row.TaxExempt == "Y")
                {
                    result.Errors.Add($"Row {lineNo}: tax exemption without certificate number");
                    continue;
                }
                order.Tax = Math.Round((subtotal - order.VolumeDiscount) * taxRate, 2);
                order.Total = subtotal - order.VolumeDiscount + order.Tax;
                if (row.Currency != "PKR")
                {
                    #pragma warning disable SYSLIB0014
                    using (var client = new WebClient())
                    {
                        try
                        {
                            var json = client.DownloadString($"https://fx.example.internal/rates/{row.Currency}");
                            var rate = JsonConvert.DeserializeObject<FxRate>(json);
                            if (rate == null || rate.Value <= 0)
                            {
                                result.Errors.Add($"Row {lineNo}: no FX rate for {row.Currency}");
                                continue;
                            }
                            order.FxRate = rate.Value;
                            order.TotalInBaseCurrency = Math.Round(order.Total * rate.Value, 2);
                        }
                        catch (WebException ex) when (ex.Status == WebExceptionStatus.Timeout)
                        {
                            result.Warnings.Add($"Row {lineNo}: FX service timed out, using last known rate");
                            order.FxRate = _pricing.LastKnownRate(row.Currency);
                            order.TotalInBaseCurrency = Math.Round(order.Total * order.FxRate, 2);
                        }
                        catch (WebException)
                        {
                            result.Errors.Add($"Row {lineNo}: FX service unavailable");
                            continue;
                        }
                    }
                    #pragma warning restore SYSLIB0014
                }
                else
                {
                    order.FxRate = 1m;
                    order.TotalInBaseCurrency = order.Total;
                }
                var warehouse = row.ShippingCountry == "PK" ? "KHI-01" : row.ShippingCountry == "AE" ? "DXB-01" : "INTL-01";
                foreach (var orderLine in order.Lines)
                {
                    var stock = _pricing.StockFor(warehouse, orderLine.Sku);
                    if (stock < orderLine.Quantity && order.Channel != SalesChannel.Wholesale)
                    {
                        if (row.AllowBackorder == "Y" || order.Status == OrderStatus.OnHold)
                        {
                            orderLine.Backordered = orderLine.Quantity - stock;
                            warnings++;
                        }
                        else
                        {
                            result.Errors.Add($"Row {lineNo}: insufficient stock for {orderLine.Sku} in {warehouse}");
                            order.Status = OrderStatus.OnHold;
                        }
                    }
                    else if (stock < orderLine.Quantity)
                    {
                        orderLine.Backordered = orderLine.Quantity - stock;
                    }
                }
                if (order.Status == OrderStatus.OnHold && order.Channel == SalesChannel.Marketplace)
                {
                    result.Warnings.Add($"Row {lineNo}: marketplace order on hold, notify channel manager");
                }
                if (order.Total > 100000m || (order.Channel == SalesChannel.Phone && order.Total > 20000m))
                {
                    order.RequiresApproval = true;
                }
                if (!string.IsNullOrWhiteSpace(row.PurchaseOrderRef) && order.Channel != SalesChannel.Wholesale)
                {
                    result.Warnings.Add($"Row {lineNo}: purchase order reference ignored for retail order");
                    row.PurchaseOrderRef = null;
                }
                if (dryRun)
                {
                    result.Validated++;
                    continue;
                }
                result.Orders.Add(order);
                result.Imported++;
            }
            result.WarningCount = warnings;
            if (result.Errors.Count > 0 && result.Imported == 0)
            {
                _logger.LogWarning("Import for {Tenant} produced no orders: {ErrorCount} errors", tenantCode, result.Errors.Count);
            }
            else if (result.Errors.Count > rows.Count / 2)
            {
                _logger.LogWarning("Import for {Tenant} rejected more than half the rows", tenantCode);
            }
            _logger.LogInformation("Imported {Count} orders for {Tenant}", result.Imported, tenantCode);
            return result;
        }

        public int CountPending(IEnumerable<Order> orders)
        {
            return orders.Count(o => o.Status == OrderStatus.Pending);
        }
    }
}
