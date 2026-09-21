# Python / Django (also Flask, FastAPI) reference for audit-async-and-dependency-injection

## Stack markers
`manage.py`, `django`/`flask`/`fastapi` in requirements. **There is no DI container in Django or Flask**: `di_lifetimes.py --stack python-django` prints "N/A" and explains. What replaces lifetimes: module-level objects (process lifetime, per worker), request objects (`request`, `g` in Flask, `Depends` in FastAPI), and thread/context locals. FastAPI `Depends` has request scope by default and app scope via `lru_cache`/`app.state` - the same captive mistakes exist there. `dependency_injector`/`injector` packages are rare; if present, apply the Singleton/Factory/Resource provider rules from their docs.

## Where the relevant code lives
`settings.py`, `apps.py` `ready()` (runs once per process), `views.py`/`api/*.py` (`async def` views), `services/*.py`, `clients/*.py` (`requests.Session`, `httpx.Client`), `middleware.py` (per-request state on `request` vs module globals), `tasks.py` (Celery), `asgi.py`/`wsgi.py`, `dependencies.py` (FastAPI), `main.py` (`lifespan`).

## Dangerous / interesting APIs and patterns
- BLOCK: in `async def` views/endpoints: `requests.get`, `time.sleep`, `subprocess.run`, sync ORM calls (`Model.objects.get()` - Django raises `SynchronousOnlyOperation` under ASGI unless wrapped in `sync_to_async`), file I/O, `boto3` calls; `asyncio.run()` inside a running loop (RuntimeError) or `loop.run_until_complete` in a view; `async_to_sync` inside an event loop thread; in sync Django: blocking is per worker (starvation = all gunicorn workers busy) - `requests` without timeout is the usual cause.
- VOID: `asyncio.create_task(coro())` result dropped (task may be GC'd mid-flight; exception logged only at GC as "Task exception was never retrieved"); `async def` called without `await` (coroutine never runs - `RuntimeWarning: coroutine was never awaited`); `loop.call_soon(async_fn)`; Celery task `.delay()` without a result backend and no error handling in the task (`except: pass`); `@receiver` signal handlers that raise (breaks the sender) vs swallow.
- CANCEL: `asyncio.wait_for` absent on awaited I/O; `httpx` calls without `timeout`; long views ignoring client disconnect (`request.is_disconnected()` in Starlette); `asyncio.CancelledError` caught and swallowed (`except Exception` does not catch it in 3.8+, but `except BaseException` does); `sync_to_async(thread_sensitive=True)` default serialising all sync work onto one thread.
- FIRE: `threading.Thread(target=...).start()` in a view; `asyncio.create_task` untracked; `ThreadPoolExecutor().submit(...)` result discarded; `celery_task.delay()` inside `transaction.atomic()` without `transaction.on_commit` (task runs before commit, sees no row); `BackgroundTasks` (FastAPI) for business-critical work (in-process, lost on restart).
- HTTP: `requests.get(...)` bare (no session - new TCP/TLS per call; also no timeout); `requests.Session()` per call; `httpx.Client()`/`AsyncClient()` per request (connection pool per call); `boto3.client(...)` per call (expensive); `aiohttp.ClientSession()` per request (warns).
- TIMEOUT: `requests.*` without `timeout=` (infinite - the single most common production hang in Python); `httpx` default 5 s (usually fine, verify); `urllib.request.urlopen` without timeout; `socket.setdefaulttimeout` unset; Celery tasks without `time_limit`/`soft_time_limit`; DB `statement_timeout` unset.
- DI (what "lifetime mismatch" means here): module-level `client = SomeClient(request.user)` or module globals assigned per request (`current_tenant = ...` at module scope - shared by all requests in the worker: a race and a cross-tenant leak); `apps.py ready()` capturing settings that vary per request; class attributes used as per-request storage; FastAPI: `Depends` on a function wrapped in `@lru_cache` that takes request-varying args (cached per args forever), `app.state.db_session` shared across requests (one session for all - like a captive DbContext); Flask: `g` misuse at module level; `threading.local()` set and never cleared (pooled threads reuse it); Django `ContextVar` set in middleware and not reset.

## What "good" looks like
```python
# module-level clients, one per process, with timeouts and retries
_session = requests.Session()
_session.mount("https://", HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.3, status_forcelist=[502, 503, 504])))
def get_rates(region: str) -> dict:
    return _session.get(f"{TAX_URL}/rates/{region}", timeout=(2, 5)).json()      # (connect, read)

# async view: nothing blocking on the loop
async def order_view(request):
    async with httpx.AsyncClient(timeout=5) as client:                          # or app-level client from lifespan
        customer, quote = await asyncio.gather(client.get(...), client.post(...))
    order = await Order.objects.acreate(...)                                     # async ORM (Django 4.1+) or sync_to_async

# FastAPI: request-scoped dependency, app-scoped client
@asynccontextmanager
async def lifespan(app): app.state.http = httpx.AsyncClient(timeout=5); yield; await app.state.http.aclose()
async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as s: yield s                                       # one session per request, never on app.state

# fire-and-forget that survives restarts, after commit
with transaction.atomic():
    invoice = Invoice.objects.create(...)
    transaction.on_commit(lambda: submit_invoice.delay(invoice.id))
@shared_task(bind=True, max_retries=3, soft_time_limit=60)
def submit_invoice(self, invoice_id): ...

# tracked background task in ASGI
task = asyncio.create_task(refresh()); _tasks.add(task); task.add_done_callback(lambda t: (_tasks.discard(t), t.exception() and log.error(t.exception())))
```

## Manual trace checklist
1. Process model: WSGI sync (blocking = worker starvation) or ASGI (blocking = loop stall)? Any `async def` view/endpoint - grep its body for sync I/O and sync ORM calls.
2. Every `requests.`/`urllib` call: `timeout=` present; session shared.
3. Module-level and class-level state written per request (`di_lifetimes.py` lists module globals assigned inside functions): tenant/user data at module scope is a cross-request leak.
4. FastAPI: `Depends` functions - per-request `yield` for DB sessions; app-level clients in `lifespan`; `@lru_cache` only on settings/config; `BackgroundTasks` not used for money/stock.
5. Celery: `.delay()` inside `atomic()` -> `on_commit`; `time_limit` set; task exceptions retried not swallowed.
6. `asyncio.create_task` and threads: tracked and logged?
7. `threading.local`/`ContextVar` set in middleware: reset in `finally`?

## Stack-specific false positives
- `requests.get` in management commands, migrations, or tests - Low, not a request path.
- `time.sleep` in retry loops of background tasks - fine if bounded.
- `sync_to_async` wrapping ORM calls in async views - correct.
- Module-level `Session()`/`httpx.Client()` - intended singleton.
- `BackgroundTasks` for non-critical work (audit log, email) with its own retry.

## Tooling
- `ruff` rules: `ASYNC100/101/102` (blocking calls in async functions, `flake8-async`), `B113`/`S113` (requests without timeout, via bandit), `RUF006` (untracked `asyncio.create_task`), `RUF029` (async function without await).
- `python -X dev` / `PYTHONASYNCIODEBUG=1` - warns on never-awaited coroutines and slow callbacks (> 100 ms on the loop = BLOCK).
- Django: `DJANGO_ALLOW_ASYNC_UNSAFE` must NOT be set in production (it hides `SynchronousOnlyOperation`); `django-silk` for per-request time.
- Runtime: `py-spy dump --pid <pid>` during a hang shows workers stuck in `socket.recv` (no timeout) or `time.sleep`; `gunicorn --timeout` kills them (symptom).

## References
CWE-833, CWE-400, CWE-390, CWE-1088, CWE-362; Django docs "Asynchronous support" (`sync_to_async`, async-safety), "Database transactions - performing actions after commit"; FastAPI "Dependencies with yield", "Lifespan events", "Background Tasks"; Python docs `asyncio` "Task - important: save a reference"; requests docs "Timeouts"; Celery "Tasks - time limits".
