# structlog reference for audit-logging-and-observability

## Processor chain

```python
import logging
import structlog

SENSITIVE = {"password", "token", "access_token", "refresh_token", "authorization", "card_number", "cvv"}

def redact(_, __, event_dict):
    for key in list(event_dict):
        if key.lower() in SENSITIVE:
            event_dict[key] = "[REDACTED]"
    return event_dict

def add_otel_ids(_, __, event_dict):
    from opentelemetry import trace
    ctx = trace.get_current_span().get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict

shared = [
    structlog.contextvars.merge_contextvars,     # request_id bound per request
    structlog.stdlib.add_logger_name,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    add_otel_ids,
    redact,
]
structlog.configure(
    processors=shared + [structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer()],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    cache_logger_on_first_use=True,
)
```
Order matters: redaction must run **before** the renderer; `merge_contextvars`
must come first or bound ids are missing. `dict_tracebacks` (structured) or
`format_exc_info` (string) turns `exc_info` into output - without one of them
`logger.exception` prints no traceback in JSON mode.

Audit points: `ConsoleRenderer()` in production (coloured text, not JSON);
`make_filtering_bound_logger(logging.DEBUG)` hard-coded; no redaction processor.

## Binding request ids

```python
# middleware (Django / Starlette)
structlog.contextvars.clear_contextvars()
structlog.contextvars.bind_contextvars(request_id=request.headers.get("X-Correlation-Id") or str(uuid4()))
```
- `django-structlog`: add `django_structlog.middlewares.RequestMiddleware`; it binds
  `request_id`, `user_id` and `ip`, and logs `request_started` / `request_finished` /
  `request_failed`. Its Celery integration forwards the id to tasks.
- FastAPI / Starlette: `asgi-correlation-id` `CorrelationIdMiddleware(header_name="X-Correlation-Id")`,
  then a processor reading `correlation_id.get()`.
- Forgetting `clear_contextvars()` leaks ids between requests on the same worker.

## stdlib integration

Third-party libraries (Django, requests, SQLAlchemy) log through stdlib `logging`.
Route them through the same pipeline with `ProcessorFormatter`:

```python
LOGGING = {
    "version": 1, "disable_existing_loggers": False,
    "formatters": {"json": {"()": structlog.stdlib.ProcessorFormatter,
                            "processor": structlog.processors.JSONRenderer(),
                            "foreign_pre_chain": shared}},
    "handlers": {"stdout": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["stdout"], "level": "INFO"},
}
```
Then configure structlog with `structlog.stdlib.ProcessorFormatter.wrap_for_formatter`
as its last processor. Without `foreign_pre_chain`, library logs skip redaction and ids.

## Calls

```python
log = structlog.get_logger()
log.info("order_placed", order_id=order.id, tenant_id=tenant.id)   # good: event name + key/values
log.info(f"order placed by {user.email}")                          # bad: unstructured, PII in text
log.info("login_attempt", **request.data)                          # bad: spreads the password into the event

try:
    reserve(order)
except StockError:
    log.exception("stock_reservation_failed", order_id=order.id)   # ERROR + traceback
    raise

try:
    reserve(order)
except StockError as e:
    log.debug("stock issue", error=str(e))                         # bad: hidden at INFO, no traceback
```

## Grep recipes

```bash
grep -rnE "structlog\.configure|ProcessorFormatter|merge_contextvars|JSONRenderer|ConsoleRenderer" --include=*.py .
grep -rnE "\.(info|debug|warning|error)\(f[\"']" --include=*.py .                        # f-string events
grep -rnE "\*\*request\.(data|POST|body)|request\.(data|body)\)" --include=*.py .
grep -rnE "bind_contextvars|RequestMiddleware|CorrelationIdMiddleware|clear_contextvars" --include=*.py .
grep -rnE -A3 "except .*:" --include=*.py . | grep -E "\.(debug|info)\("                  # low-level logging in except
```
