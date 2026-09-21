# Python / Django reference for audit-frontend-memory-leak

This skill audits frontend memory. A Django (Channels), Flask-SocketIO or
FastAPI backend in the same repo matters as the server end of WebSocket/SSE
connections, and - when the UI is server-rendered with HTMX/Alpine/jQuery
sprinkles - as the place that ships the frontend JavaScript. Check those;
defer the rest to `audit-backend-resource-leak`.

## Stack markers

`requirements.txt`/`pyproject.toml` with `channels`, `channels-redis`, `django-eventstream`,
`flask-socketio`, `sse-starlette`, `websockets`; `asgi.py` with `ProtocolTypeRouter`.
Frontend counterpart: `WebSocket`, `EventSource`, `socket.io-client`, or HTMX `hx-ws`/`hx-sse`
extensions in templates.

## Where the relevant code lives

`consumers.py` (`AsyncWebsocketConsumer.connect/disconnect`), `routing.py`, SSE views
(`StreamingHttpResponse` with `text/event-stream`), `static/js/**` and `templates/**` for
server-rendered pages (inline `<script>` blocks that register listeners on every partial
swap), Flask `@socketio.on('connect')` handlers.

## Dangerous / interesting APIs and patterns (this skill's slice only)

- Consumer `connect()` doing `group_add` with no `disconnect()` doing `group_discard`: each
  leaked client socket leaves a stale channel-layer group member (Redis memory grows).
- Module-level registries of consumers/sockets (`CONNECTED = {}`) written in `connect` and never
  cleaned.
- SSE `StreamingHttpResponse` generators that loop forever without catching the client
  disconnect (`GeneratorExit`) and that run under a sync worker (thread pinned per leaked client).
- Server-rendered UIs: HTMX partial swaps that re-run inline `<script>` adding
  `document.addEventListener(...)` on every swap (listeners stack in the browser - the
  frontend finding lives in the template, `leak_scan.py` will flag it).
- `hx-trigger="every 5s"` polling on elements that are swapped out: fine (HTMX cancels), but a
  hand-written `setInterval` in an inline script is not.
- Broadcasting large payloads per tick (`group_send` with full querysets) - amplifies the
  client leak; note in Impact.

## What "good" looks like

```python
class InventoryConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.group = f"tenant_{self.scope['user'].tenant_id}"
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()
    async def disconnect(self, code):
        await self.channel_layer.group_discard(self.group, self.channel_name)
```
```python
def events(request):
    def stream():
        try:
            while True:
                yield f"data: {next_event()}\n\n"
        except GeneratorExit:      # client went away
            cleanup()
    return StreamingHttpResponse(stream(), content_type="text/event-stream")
```
Template pairing: put listener registration in a module script loaded once (not inside a
swapped partial), or use `htmx:afterSwap` with idempotent guards.

## Manual trace checklist

1. Locate consumers/SSE views and the client code that connects (module script or template).
   One connection per session or per page fragment? Client side is the finding.
2. `connect`/`disconnect` symmetry for every `group_add`, registry write, or task spawn.
3. SSE generators handle `GeneratorExit`; async views used for streaming.
4. Server-rendered templates: inline scripts inside HTMX/Turbo partials that add listeners or
   timers.

## Stack-specific false positives

- Channels groups on a Redis layer expire (`group_expiry`, default 86400 s) - a missing
  `group_discard` is Medium, not High, unless churn is high.
- HTMX built-in polling/SSE extensions manage their own teardown.

## Tooling

`python manage.py shell -c "from channels.layers import get_channel_layer ..."` to count group
members; `redis-cli --bigkeys` on the channel layer while the frontend heap-snapshot procedure runs.

## Deferred to sibling skills

DB connections, file handles, Celery tasks, caches: `audit-backend-resource-leak`. WebSocket
auth: `audit-authz-and-access-control`.

## References

Django Channels consumers: https://channels.readthedocs.io/en/latest/topics/consumers.html;
HTMX events: https://htmx.org/events/; CWE-401, CWE-772, CWE-400.
