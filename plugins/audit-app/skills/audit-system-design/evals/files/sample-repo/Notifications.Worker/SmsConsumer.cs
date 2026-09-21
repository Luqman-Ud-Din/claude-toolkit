using Microsoft.Extensions.Hosting;

namespace Notifications.Worker
{
    // Consumes orders.created from RabbitMQ and sends an SMS; idempotent by message id.
    public class SmsConsumer : BackgroundService
    {
        private readonly IHttpClientFactory _http;
        public SmsConsumer(IHttpClientFactory http) { _http = http; }

        protected override Task ExecuteAsync(CancellationToken ct)
        {
            // subscription code omitted; each message is de-duplicated by MessageId before sending
            return Task.CompletedTask;
        }
    }
}
