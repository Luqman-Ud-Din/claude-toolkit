using System.Globalization;
using System.Text;
using OrderService.Api.Models;

namespace OrderService.Api.Legacy
{
    public class LegacyCsvExporter
    {
        private const string Separator = ";";

        public string Export(IEnumerable<Order> orders)
        {
            var sb = new StringBuilder();
            sb.AppendLine("OrderNumber;Customer;Total;Status");
            foreach (var order in orders)
            {
                sb.Append(order.OrderNumber).Append(Separator);
                sb.Append(Escape(order.CustomerName)).Append(Separator);
                sb.Append(order.Total.ToString("0.00", CultureInfo.InvariantCulture)).Append(Separator);
                sb.AppendLine(order.Status.ToString());
            }
            return sb.ToString();
        }

        private static string Escape(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return string.Empty;
            }
            return value.Contains(Separator) ? "\"" + value.Replace("\"", "\"\"") + "\"" : value;
        }
    }
}
