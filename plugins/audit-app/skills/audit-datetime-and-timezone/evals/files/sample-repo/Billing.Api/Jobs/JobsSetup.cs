using System;
using Hangfire;

namespace Billing.Api.Jobs
{
    public static class JobsSetup
    {
        public static void Register()
        {
            // ISSUE: cron with no zone. Hangfire evaluates this in UTC, but the job
            // sends "end of business day" statements to Pakistani branches, so it
            // fires at 07:00 local instead of 02:00.
            RecurringJob.AddOrUpdate<StatementJob>("statements", j => j.SendDailyStatements(), "0 2 * * *");

            // Correct (negative case): explicit zone on a local wall-clock schedule.
            RecurringJob.AddOrUpdate<TrialJob>("trial-expiry", j => j.ExpireTrials(), "0 3 * * *",
                new RecurringJobOptions { TimeZone = TimeZoneInfo.FindSystemTimeZoneById("Asia/Karachi") });
        }
    }

    public class StatementJob { public void SendDailyStatements() { } }
    public class TrialJob { public void ExpireTrials() { } }
}
