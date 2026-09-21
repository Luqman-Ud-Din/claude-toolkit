using System;

namespace Billing.Api.Subscriptions
{
    public class Subscription
    {
        public int Id { get; set; }
        public int CustomerId { get; set; }

        // Correct (negative case): offset-aware instant, maps to datetimeoffset.
        public DateTimeOffset CreatedAt { get; set; }

        // ISSUE: instant stored in a zone-less column (see migrations/001_init.sql:
        // TrialEndsAt datetime2). Nothing documents whether it is UTC or server-local;
        // TrialJob compares it to DateTime.Now.
        public DateTime TrialEndsAt { get; set; }

        // Correct (negative case): a true date-only concept using DateOnly -> date column.
        public DateOnly BillingAnchorDate { get; set; }
    }

    public class Branch
    {
        public int Id { get; set; }
        // Correct (negative case): the branch's zone is stored, not guessed.
        public string IanaTimeZone { get; set; } = "Asia/Karachi";
    }
}
