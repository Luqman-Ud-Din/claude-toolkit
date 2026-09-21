# OpenTelemetry baseline for audit-logging-and-observability

OpenTelemetry (OTel) is the vendor-neutral way to export traces, metrics and
logs. Treat it as the yardstick even when the project uses a vendor agent
(Datadog, New Relic, App Insights): the questions are the same.

## The three signals

| Signal | Answers | Minimum expectation |
|---|---|---|
| Traces | Where did this request spend its time, which downstream failed? | Inbound HTTP, outbound HTTP, DB and queue spans per service |
| Metrics | Is the service healthy right now? | Request rate, error rate, latency histogram, runtime (CPU, memory, GC, pools) |
| Logs | What exactly happened on this request? | Structured records carrying `trace_id` / `span_id` |

## Context propagation

- **W3C `traceparent`** (`00-<trace-id>-<span-id>-<flags>`) and `tracestate` are
  the standard headers; configure `OTEL_PROPAGATORS=tracecontext,baggage`. A custom
  `X-Correlation-Id` is fine alongside it, but map one to the other so logs and
  traces share an id.
- Propagation must cover every hop: browser -> gateway -> service -> outbound HTTP ->
  queue message headers -> worker. Gateways (Ocelot, nginx, API Management) must
  forward the header, not strip it.
- **Baggage** is copied to every downstream call and often into span attributes and
  third-party vendors. Never put user email, names, tokens or tenant secrets in
  baggage; opaque ids only.

## Resource attributes and sampling

- `service.name` (`OTEL_SERVICE_NAME`), `service.version`, `deployment.environment`
  (`OTEL_RESOURCE_ATTRIBUTES=deployment.environment=prod,service.version=1.4.2`).
  Without `service.name` everything lands as `unknown_service`.
- Sampling: `OTEL_TRACES_SAMPLER=parentbased_traceidratio`,
  `OTEL_TRACES_SAMPLER_ARG=0.1`. Parent-based keeps a trace whole across services.
  Keep error traces with tail sampling in the collector (`tail_sampling` processor).
- Exporter: `OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317`,
  `OTEL_EXPORTER_OTLP_PROTOCOL=grpc|http/protobuf`. `OTEL_TRACES_EXPORTER=console`
  or `none` in production means nothing is exported.

## Collector with redaction

```yaml
processors:
  attributes/scrub:
    actions:
      - { key: http.request.header.authorization, action: delete }
      - { key: enduser.id, action: hash }
  redaction:
    allow_all_keys: true
    blocked_values: ["[0-9]{13,16}", "eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+"]
  batch: {}
service:
  pipelines:
    traces: { receivers: [otlp], processors: [attributes/scrub, redaction, batch], exporters: [otlphttp] }
```

## Setup per stack

- **.NET**: `builder.Services.AddOpenTelemetry().ConfigureResource(r => r.AddService("orders-api"))
  .WithTracing(t => t.AddAspNetCoreInstrumentation().AddHttpClientInstrumentation().AddOtlpExporter())
  .WithMetrics(m => m.AddAspNetCoreInstrumentation().AddRuntimeInstrumentation().AddOtlpExporter());`
  logs: `builder.Logging.AddOpenTelemetry(o => o.AddOtlpExporter())` or the Serilog OTLP sink.
- **Java**: `-javaagent:opentelemetry-javaagent.jar` (zero-code) or Spring Boot 3
  `micrometer-tracing-bridge-otel` + `opentelemetry-exporter-otlp`; MDC gets
  `traceId`/`spanId` automatically.
- **Node**: `@opentelemetry/sdk-node` + `@opentelemetry/auto-instrumentations-node`,
  loaded **before** the app (`node --import ./instrumentation.mjs server.js` or
  `--require`); loading it after `express` is required silently misses spans.
  pino/winston instrumentations inject `trace_id` into records.
- **Python**: `pip install opentelemetry-distro opentelemetry-exporter-otlp`;
  `opentelemetry-bootstrap -a install`; run `opentelemetry-instrument gunicorn app.wsgi`;
  `OTEL_PYTHON_LOG_CORRELATION=true` adds `otelTraceID` to log records.
- **Browser**: `@opentelemetry/sdk-trace-web` with fetch/XHR instrumentation and
  `propagateTraceHeaderCorsUrls`.

## Log-trace correlation

Every log record written during a request should carry `trace_id` (and ideally
`span_id`). Check the formatter output or a sample line: Serilog span enricher or
`Activity.Current`, Logback `%X{traceId}`, pino `mixin` / OTel pino instrumentation,
Python `OTEL_PYTHON_LOG_CORRELATION`, structlog processor reading the current span.

## Evidence that telemetry is actually exported

1. SDK/agent dependency present **and** initialised in the entry point.
2. Exporter endpoint configured for production (env, Helm values, compose), not
   only in `appsettings.Development.json`.
3. Collector config or vendor agent deployed (compose service, DaemonSet, sidecar).
4. A sample trace or dashboard screenshot from the user; otherwise mark `?`.

## Common gaps

- SDK referenced but no exporter registered - spans are created and dropped.
- Inbound HTTP instrumented but outbound `HttpClient`/`axios`/`requests` not, so the chain breaks at the first downstream call.
- Background workers and queue consumers start new root traces instead of continuing the producer's context.
- `service.name` identical across services, or environment not tagged.
- 100 percent sampling in production with no cost control, or 1 percent with no error retention.
- Span attributes holding SQL parameters, request bodies or `enduser.id` set to an email (PII).
