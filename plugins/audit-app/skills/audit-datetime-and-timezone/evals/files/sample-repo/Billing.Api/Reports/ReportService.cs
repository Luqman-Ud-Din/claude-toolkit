using System;
using System.Linq;
using Billing.Api.Subscriptions;

namespace Billing.Api.Reports
{
    public interface IBillingRepository
    {
        IQueryable<Subscription> Subscriptions { get; }
    }

    public class ReportService
    {
        private readonly IBillingRepository _repo;
        private readonly TimeProvider _clock;

        public ReportService(IBillingRepository repo, TimeProvider clock)
        {
            _repo = repo;
            _clock = clock;
        }

        // ISSUE: local-time call used for a cutoff. DateTime.Today is the server's
        // zone; CreatedAt is an offset-aware instant. The "today" window is wrong for
        // every branch not in the server's zone and is 23/25 hours on DST days.
        public int TrialsStartedToday()
        {
            var start = DateTime.Today;
            var end = start.AddDays(1);
            return _repo.Subscriptions.Count(s => s.CreatedAt >= start && s.CreatedAt < end);
        }

        // ISSUE: naive comparison. TrialEndsAt has no documented zone and is compared
        // with DateTime.Now (server local).
        public bool IsTrialExpired(Subscription s)
        {
            return s.TrialEndsAt < DateTime.Now;
        }

        // Correct (negative case): window computed in the branch's stored zone,
        // converted to UTC, with an injectable clock.
        public int TrialsStartedOn(DateOnly day, Branch branch)
        {
            var tz = TimeZoneInfo.FindSystemTimeZoneById(branch.IanaTimeZone);
            var localStart = day.ToDateTime(TimeOnly.MinValue);
            var localEnd = day.AddDays(1).ToDateTime(TimeOnly.MinValue);
            var startUtc = new DateTimeOffset(localStart, tz.GetUtcOffset(localStart)).ToUniversalTime();
            var endUtc = new DateTimeOffset(localEnd, tz.GetUtcOffset(localEnd)).ToUniversalTime();
            return _repo.Subscriptions.Count(s => s.CreatedAt >= startUtc && s.CreatedAt < endUtc);
        }

        public DateTimeOffset NowUtc() => _clock.GetUtcNow();
    }
}
