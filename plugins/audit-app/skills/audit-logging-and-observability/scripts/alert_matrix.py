#!/usr/bin/env python3
"""Build the alert coverage matrix (signal -> alert exists Y/N/? -> source file) from the
alert-rule files committed to a repository.

Usage:
    python alert_matrix.py <repo_root> [--out alerts.json] [--md alert-matrix.md]

Rule files recognised (read-only):
  * Prometheus / Alertmanager rule files  - YAML with `groups:` and `- alert:` + `expr:`;
    Alertmanager routing (`route:` + `receivers:`) and PrometheusRule CRDs.
  * Azure Monitor - ARM JSON / Bicep (`Microsoft.Insights/metricAlerts`, `scheduledQueryRules`,
    `activityLogAlerts`, `actionGroups`) and Terraform `azurerm_monitor_*_alert*`.
  * Datadog - monitor JSON (`"type": "metric alert" | "query alert" | "log alert" | "service check"`)
    and Terraform `datadog_monitor`.
  * Grafana - alerting provisioning YAML/JSON (`apiVersion` + `groups` + `rules` + `condition`,
    or dashboard panels with an `"alert"` block) and Terraform `grafana_rule_group`.
  * CloudWatch - CloudFormation/SAM `AWS::CloudWatch::Alarm`, Terraform `aws_cloudwatch_metric_alarm`,
    `aws cloudwatch put-metric-alarm` in scripts, CDK `new cloudwatch.Alarm(` / `.createAlarm(`.

Each rule is cut out of its file (from its start marker to the next one), and its text is
matched against the signal keywords from references/alert-signals.md.

Matrix rule: Y = at least one rule in the repo covers the signal; N = rule files exist but
none covers it; ? = no rule files in the repo at all (alerting may live in a SaaS console -
ask for an export; never report ? as Y).

Output JSON: {"root", "generated_at", "rule_files": [...], "rules": [{"file", "line", "tool",
"name", "signals"}], "routing": [...], "exporters": [...], "matrix": [{"signal", "label",
"alert_exists", "sources": ["file:line (name)"]}]}
"""
import argparse
import importlib.util
import json
import os
import re
import sys
from datetime import datetime, timezone

def _audit_core_skills_dir():
    """Resolve the explicit core installation, or the original sibling layout."""
    env = os.environ.get("AUDIT_CORE_ROOT")
    if env:
        skills = os.path.join(env, "skills")
        if os.path.isdir(os.path.join(skills, "audit-code-scan")):
            return skills
        sys.exit("AUDIT_CORE_ROOT does not contain audit-core skills: " + env)
    sibling = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if os.path.isdir(os.path.join(sibling, "audit-code-scan")):
        return sibling
    sys.exit("audit-core is unavailable. Enable audit-core and restart Claude Code, "
             "or set AUDIT_CORE_ROOT to its plugin directory when running manually.")

_SKILLS = _audit_core_skills_dir()
_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
try:
    _spec = importlib.util.spec_from_file_location("audit_code_scan_repo_walk", _WALK)
    repo_walk = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(repo_walk)
except (FileNotFoundError, AttributeError, ImportError):
    sys.exit("audit-code-scan must be reachable from this skill (audit-core plugin or sibling layout; expected " + _WALK + ")")
EXT = {".yml", ".yaml", ".json", ".bicep", ".tf", ".sh", ".ps1", ".ts", ".js", ".py", ".rules", ".libsonnet", ".jsonnet"}
MAX_BYTES = 2_000_000
MANIFEST_NAMES = {"package.json", "pom.xml", "requirements.txt", "dockerfile"}

SIGNALS = [
    ("error_rate", "Error rate (5xx / exceptions)",
     r"\b5\d\d\b|5xx|status=~\"5|code=~\"5|error[_ \-]?rate|errors?_total|http5xx|5XXError|HTTPCode_\w*5XX|exceptions?\b|failed[_ ]?requests|requests/failed|status_code\s*>=\s*500"),
    ("latency", "Latency (p95/p99)",
     r"latency|duration|histogram_quantile|\bp9[059]\b|response[_ ]?time|TargetResponseTime|http_server_request_duration|requests/duration|percentile"),
    ("saturation_cpu", "Saturation - CPU", r"\bcpu|CPUUtilization|Percentage CPU|process_cpu"),
    ("saturation_memory", "Saturation - memory", r"memory|MemoryUtilization|working_?set|\bheap|container_memory|Available Memory|\boom"),
    ("saturation_pool_queue", "Saturation - pool / queue depth",
     r"queue|backlog|\bpool\b|threadpool|thread_pool|connections?_(?:active|used|max)|ApproximateNumberOfMessages|consumer_lag|\blag\b|DatabaseConnections|active_connections"),
    ("availability_uptime", "Availability / uptime probe",
     r"\bup\s*==\s*0|probe_success|availability|uptime|health[_ ]?check|synthetic|HealthyHostCount|UnHealthyHostCount|StatusCheckFailed|/health"),
    ("dependency_health", "Dependency health (DB, broker, cache)",
     r"database|\bdb_|redis|rabbit|kafka|broker|\bcache|\bsql|postgres|mysql|mongo|dependenc|pg_up|mysql_up|redis_up"),
    ("security_failed_login", "Security - failed-login spike / lockouts",
     r"failed[_ \-]?log[io]n|login[_ \-]?fail|auth(?:entication)?[_ \-]?fail|lockout|invalid[_ \-]?credentials|\b401\b"),
    ("security_authz_denied", "Security - permission denied spike", r"denied|forbidden|\b403\b|access[_ \-]?denied|authz"),
    ("security_admin_action", "Security - admin action / export / delete",
     r"\badmin|role[_ \-]?chang|privilege|data[_ \-]?export|bulk[_ \-]?delete|audit[_ \-]?event"),
    ("job_failures", "Background job failures / backlog",
     r"\bjobs?[_ \-]?(?:fail|error|backlog|retr)|failed[_ \-]?jobs?|hangfire|celery|sidekiq|cronjob|kube_job_status_failed|dead[_ \-]?letter|\bdlq"),
    ("cert_expiry", "Certificate expiry", r"\bcert|\bssl|\btls|x509|expir"),
    ("disk_space", "Disk space", r"\bdisk|filesystem|node_filesystem|volume|FreeStorageSpace|storage[_ ]?(?:used|free)"),
]
SIGNAL_RX = [(sid, label, re.compile(rx, re.I)) for sid, label, rx in SIGNALS]

# (tool, file-level detector, rule start marker, name capture)
TOOLS = [
    ("prometheus", re.compile(r"^\s*groups\s*:|kind\s*:\s*PrometheusRule", re.M),
     re.compile(r"^\s*-\s*alert\s*:\s*[\"']?([\w\-. ]+)", re.M)),
    ("azure-monitor", re.compile(r"Microsoft\.Insights/(?:metricAlerts|scheduledQueryRules|activityLogAlerts)|azurerm_monitor_\w*alert", re.I),
     re.compile(r"(?:resource\s+\w+\s+'Microsoft\.Insights/(?:metricAlerts|scheduledQueryRules|activityLogAlerts)[^']*'|\"type\"\s*:\s*\"Microsoft\.Insights/(?:metricAlerts|scheduledQueryRules|activityLogAlerts)\"|resource\s+\"azurerm_monitor_\w*alert\w*\"\s+\"([\w\-]+)\")", re.I)),
    ("datadog", re.compile(r"\"type\"\s*:\s*\"(?:metric|query|log|service check|composite|slo) alert\"|\"type\"\s*:\s*\"service check\"|resource\s+\"datadog_monitor\"", re.I),
     re.compile(r"\"name\"\s*:\s*\"([^\"]+)\"|resource\s+\"datadog_monitor\"\s+\"([\w\-]+)\"", re.I)),
    ("grafana", re.compile(r"(?:^\s*apiVersion\s*:\s*1[\s\S]*^\s*groups\s*:[\s\S]*condition\s*:)|\"alert\"\s*:\s*\{|grafana_rule_group|\"condition\"\s*:\s*\"[A-Z]\"", re.M),
     re.compile(r"^\s*-\s*uid\s*:\s*([\w\-]+)|^\s*title\s*:\s*[\"']?([^\"'\n]+)|\"title\"\s*:\s*\"([^\"]+)\"", re.M)),
    ("cloudwatch", re.compile(r"AWS::CloudWatch::Alarm|aws_cloudwatch_metric_alarm|put-metric-alarm|cloudwatch\.Alarm\(|\.createAlarm\(", re.I),
     re.compile(r"(?:^\s*([\w]+)\s*:\s*\n\s*Type\s*:\s*[\"']?AWS::CloudWatch::Alarm|resource\s+\"aws_cloudwatch_metric_alarm\"\s+\"([\w\-]+)\"|put-metric-alarm[^\n]*--alarm-name\s+[\"']?([\w\-]+)|new\s+cloudwatch\.Alarm\(\s*this\s*,\s*[\"']([\w\-]+)|\.createAlarm\(\s*this\s*,\s*[\"']([\w\-]+))", re.M | re.I)),
]
ROUTING_RX = re.compile(r"^\s*receivers\s*:|Microsoft\.Insights/actionGroups|azurerm_monitor_action_group|pagerduty|opsgenie|notification_channel|contact_points|contactPoints|\"notify_no_data\"|@slack-|@pagerduty|AlarmActions|alarm_actions|sns_topic", re.I | re.M)
EXPORTER_RX = re.compile(r"AddOpenTelemetry|AddOtlpExporter|@opentelemetry/sdk-node|opentelemetry-instrument|opentelemetry\.sdk|micrometer-registry-\w+|micrometer-tracing|prom-client|prometheus_client|prometheus-net|UseOpenTelemetry|OTEL_EXPORTER_OTLP_ENDPOINT|dd-trace|ddtrace|newrelic|applicationinsights|elastic-apm", re.I)


def read(path):
    try:
        if os.path.getsize(path) > MAX_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read()
    except OSError:
        return None


def cut_rules(text, marker):
    starts = [m for m in marker.finditer(text)]
    rules = []
    for n, m in enumerate(starts):
        end = starts[n + 1].start() if n + 1 < len(starts) else min(len(text), m.start() + 4000)
        name = next((g for g in m.groups() if g), None) if m.groups() else None
        rules.append((text.count("\n", 0, m.start()) + 1, (name or "").strip(), text[m.start():end]))
    return rules


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args()
    root = os.path.abspath(a.root)
    rule_files, rules, routing, exporters = [], [], [], []
    for full in repo_walk.iter_files(root, exts=EXT | {".csproj"}, names=MANIFEST_NAMES, max_bytes=None):
        fn = os.path.basename(full)
        ext = os.path.splitext(fn)[1].lower()
        rel = repo_walk.rel(root, full)
        text = read(full)
        if text is None:
            continue
        if EXPORTER_RX.search(text):
            m = EXPORTER_RX.search(text)
            exporters.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1} ({m.group(0)})")
        if ext not in EXT:
            continue
        file_tools = []
        for tool, detector, marker in TOOLS:
            if tool == "prometheus" and not re.search(r"^\s*-\s*alert\s*:", text, re.M):
                continue
            if not detector.search(text):
                continue
            file_tools.append(tool)
            for line, name, body in cut_rules(text, marker):
                sigs = [sid for sid, _, rx in SIGNAL_RX if rx.search(body)]
                rules.append({"file": rel, "line": line, "tool": tool, "name": name, "signals": sigs})
        if file_tools:
            rule_files.append({"file": rel, "tools": file_tools})
        if ROUTING_RX.search(text) and (file_tools or re.search(r"alertmanager|action_?group|notification", fn + text[:2000], re.I)):
            m = ROUTING_RX.search(text)
            routing.append(f"{rel}:{text.count(chr(10), 0, m.start()) + 1}")
    matrix = []
    for sid, label, _ in SIGNAL_RX:
        srcs = [f"{r['file']}:{r['line']}" + (f" ({r['name']})" if r["name"] else "") for r in rules if sid in r["signals"]]
        exists = "Y" if srcs else ("N" if rule_files else "?")
        matrix.append({"signal": sid, "label": label, "alert_exists": exists, "sources": srcs})
    res = {"root": root, "generated_at": datetime.now(timezone.utc).isoformat(), "rule_files": rule_files,
           "rules": rules, "routing": routing, "exporters": exporters, "matrix": matrix}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(res, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        o = ["### Alert coverage matrix", "", "| Signal | Alert exists | Source file | Routed to on-call |", "|---|---|---|---|"]
        for row in matrix:
            src = "; ".join(f"`{s}`" for s in row["sources"][:3]) or "-"
            routed = ("yes (" + ", ".join(f"`{r}`" for r in routing[:2]) + ")") if (routing and row["alert_exists"] == "Y") else ("?" if row["alert_exists"] != "N" else "-")
            o.append(f"| {row['label']} | {row['alert_exists']} | {src} | {routed} |")
        o += ["", "Legend: Y = rule found in the repo, N = rule files exist but none covers the signal, "
              "? = no alert-rule files in the repo (may live in a SaaS console - request an export).", "",
              f"Rule files: {', '.join('`' + r['file'] + '`' for r in rule_files) or 'none'}", "",
              f"Telemetry exporters seen: {', '.join('`' + e + '`' for e in exporters[:8]) or 'none'}", ""]
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(o))
    print(json.dumps({"rule_files": len(rule_files), "rules": len(rules),
                      "matrix": {m["signal"]: m["alert_exists"] for m in matrix}}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
