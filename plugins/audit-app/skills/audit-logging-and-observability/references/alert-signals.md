# Alert signal catalogue for audit-logging-and-observability

`scripts/alert_matrix.py` fills the alert coverage matrix with these signal ids.
Keep the ids identical in the script, this file and the report.

## Signals

| id | Signal | Why it matters | Good threshold / window | Typical rule shape per tool |
|---|---|---|---|---|
| error_rate | 5xx / unhandled exception rate | first sign of a bad deploy or broken dependency | > 2 percent of requests for 5 min, or SLO burn rate | Prometheus `rate(http_requests_total{status=~"5.."}[5m]) / rate(http_requests_total[5m])`; CloudWatch `5XXError`; Azure `requests/failed` |
| latency | p95 / p99 response time | slow is the new down; users leave before errors appear | p95 above SLO (e.g. 800 ms) for 10 min | `histogram_quantile(0.95, sum by (le) (rate(http_request_duration_seconds_bucket[5m])))`; CloudWatch `Latency` / `TargetResponseTime` |
| saturation_cpu | CPU utilisation / throttling | predicts latency collapse and autoscaling limits | > 85 percent for 15 min | `CPUUtilization`, `Percentage CPU`, `container_cpu_cfs_throttled_seconds_total` |
| saturation_memory | memory working set / OOM kills | leaks end in restarts and lost requests | > 90 percent of limit for 10 min; any OOMKilled | `container_memory_working_set_bytes`, `MemoryUtilization`, `kube_pod_container_status_last_terminated_reason` |
| saturation_pool_queue | connection pool, thread pool, queue depth | exhaustion looks like a hang, not an error | pool in use > 90 percent; oldest message older than N min | `hikaricp_connections_pending`, `dotnet_threadpool_queue_length`, `ApproximateAgeOfOldestMessage`, `rabbitmq_queue_messages_ready` |
| availability_uptime | health check / synthetic probe | detects a total outage from outside | 2 consecutive failures from 2 locations | `probe_success == 0` (blackbox exporter), App Insights availability test, Route 53 health check |
| dependency_health | DB / broker / cache reachability | the app is up but useless | readiness check reports a dependency down for 2 min | `/health/ready` degraded, `pg_up == 0`, `redis_up == 0` |
| security_failed_login | failed-login spike, lockouts | credential stuffing and brute force | > N failures per 5 min per IP, or 3x baseline overall | log query on `auth.login_failed` / `LoginFailed` events |
| security_authz_denied | permission denied (403) spike | probing for broken access control / IDOR | 403 rate above 3x baseline for 10 min | `http_requests_total{status="403"}`, log query on `access_denied` |
| security_admin_action | admin / role change, data export, bulk delete | insider misuse and account takeover show up here | any occurrence outside a change window; notify rather than page | log query on `role_changed`, `user.impersonate`, `export`, `bulk_delete` |
| job_failures | background job failures / backlog | silent data loss: invoices not sent, sync stopped | any failed job after retries; backlog > N for 30 min | Hangfire failed count, Celery `task-failed`, `kube_job_status_failed`, dead-letter queue depth > 0 |
| cert_expiry | TLS certificate expiry | a hard, fully predictable outage | < 14 days left | `probe_ssl_earliest_cert_expiry - time() < 14*86400`; ACM `DaysToExpiry` |
| disk_space | disk / volume free space | full disks stop databases and log shipping | < 15 percent free | `node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.15`; `disk_used_percent` |

## Recognising rules per tool

**Prometheus / Alertmanager** - YAML with `groups:` -> `rules:` -> `- alert: Name`,
`expr:`, `for:`, `labels: {severity: page}`; routing in `alertmanager.yml`
(`route:`, `receivers:`). Keywords: `http_requests_total`, `status=~"5.."`,
`histogram_quantile`, `probe_success`, `node_filesystem_avail_bytes`. Kubernetes
`kind: PrometheusRule` CRDs use the same shape under `spec.groups`.

**Azure Monitor** - ARM JSON `"type": "Microsoft.Insights/metricAlerts"` (with
`criteria.allOf[].metricName` such as `requests/failed`, `Percentage CPU`, `Http5xx`),
`Microsoft.Insights/scheduledQueryRules` (KQL `query`), `Microsoft.Insights/webtests`
(availability); Bicep `resource x 'Microsoft.Insights/metricAlerts@2018-03-01'`;
Terraform `azurerm_monitor_metric_alert`, `azurerm_monitor_scheduled_query_rules_alert_v2`,
`azurerm_application_insights_standard_web_test`; routing via `actionGroups` /
`azurerm_monitor_action_group`.

**Datadog** - monitor JSON with `"type": "metric alert"`, `"query alert"`, `"log alert"`
or `"service check"` and a `"query"` such as
`avg(last_5m):sum:trace.http.request.errors{env:prod} / sum:trace.http.request.hits{env:prod} > 0.02`;
Terraform `datadog_monitor`; routing by `@pagerduty-...` / `@slack-...` handles in `message`.

**Grafana alerting** - provisioning YAML under `provisioning/alerting/` with
`apiVersion: 1`, `groups:` -> `rules:` -> `title`, `condition`, `data[].model.expr`;
JSON exports with `"condition"` and `"noDataState"`; contact points under
`contactPoints:`; Terraform `grafana_rule_group`.

**CloudWatch** - CloudFormation/SAM `Type: AWS::CloudWatch::Alarm` with `MetricName:`
(`5XXError`, `HTTPCode_Target_5XX_Count`, `Latency`, `TargetResponseTime`,
`CPUUtilization`, `FreeStorageSpace`, `ApproximateAgeOfOldestMessage`); Terraform
`aws_cloudwatch_metric_alarm`; CDK `new cloudwatch.Alarm(`; log-based alarms via
`AWS::Logs::MetricFilter`; routing via `AlarmActions` -> SNS topic.

## Y / N / ? rule

- **Y** - a rule file in the repo defines an alert for the signal. Record the file and rule name.
- **N** - rule files exist in the repo, but none covers this signal. This is a real gap.
- **?** - no rule files exist in the repo at all. Alerting may live in a SaaS console
  (Datadog UI, Grafana Cloud, Azure portal). Do not write N; request an export
  (Datadog monitor JSON, `az monitor metrics alert list -o json`,
  `aws cloudwatch describe-alarms`) and list it under Not checked.

A rule that exists but routes nowhere (no receiver, no action group, no SNS
subscription) is still `Y`, with the gap note "not routed" - nobody gets paged.

## What good looks like

- Symptom-based paging (error rate, latency, availability) routed to an on-call
  rotation (PagerDuty, Opsgenie, Teams/Slack with escalation); cause-based signals
  (CPU, disk) notify rather than page.
- SLO burn-rate alerts: multi-window, multi-burn-rate (for example, 2 percent of a
  30-day error budget spent in 1 hour, confirmed over 5 minutes, pages; 10 percent in
  6 hours opens a ticket).
- Every alert carries a runbook link and service/environment labels.
- Security signals feed the same routing, or a SIEM with its own on-call.
