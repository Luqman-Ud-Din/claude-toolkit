# Python / Django (also Flask, FastAPI) reference for audit-backend-resource-leak

## Stack markers
`manage.py`, `requirements.txt`/`pyproject.toml` with `django`, `flask`, or `fastapi`. Sub-variants: WSGI (gunicorn sync workers - a leak is bounded by `--max-requests`, which is a mitigation, not a fix) vs ASGI (uvicorn/daphne, long-lived event loop - leaks accumulate for the process lifetime); Celery/RQ/Django-Q workers; Django Channels consumers.

## Where the relevant code lives
`settings.py` (`CACHES`, `DATABASES.CONN_MAX_AGE`), `apps.py` `ready()` (runs once - anything registered here is process-lifetime), `views.py`/`api/*.py`, `tasks.py` (Celery), `management/commands/`, `consumers.py` (Channels), `middleware.py`, `signals.py`, any module-level `list`/`dict`/`set`, `utils/cache*.py`.

## Dangerous / interesting APIs and patterns
- Disposal: `open(` without `with`; `tempfile.NamedTemporaryFile(delete=False)` never removed; `requests.get(..., stream=True)` response never `close()`d; `requests.Session()` per call (connection pool per call); `httpx.Client()`/`AsyncClient()` per request instead of one shared; `psycopg2.connect`/`sqlite3.connect` outside Django ORM without `close()`; `subprocess.Popen` without `wait()`/`communicate()` (zombie processes and pipes); `zipfile.ZipFile`, `PIL.Image.open`, `openpyxl.load_workbook` without `with`/`close()`; `ThreadPoolExecutor()` created per request without `with`; `asyncio.create_task` result discarded (task garbage-collected mid-flight, exceptions lost).
- Timers/tasks: `threading.Timer` per request; `asyncio.create_task` in a request path never awaited or cancelled; `loop.call_later` in a view.
- Growth: module-level `list`/`dict` with `append`/`[key] =` and no removal; `functools.lru_cache` with `maxsize=None`; `@cache` on methods (keeps `self` alive for every instance); class attributes used as caches; `logging` handlers added per request (`logger.addHandler` inside a function); Django signal `connect()` inside a function called repeatedly without `weak=True`/`dispatch_uid`.
- Cache: `CACHES` backend `LocMemCache` without `OPTIONS.MAX_ENTRIES` (default 300 - bounded but often raised to huge values); `cache.set(key, value)` with `timeout=None` (never expires); `cachetools` `Cache` without `maxsize`; hand-rolled dict caches keyed by user input.
- Hot-path allocation: reading uploads into memory (`request.FILES['f'].read()`) without `DATA_UPLOAD_MAX_MEMORY_SIZE`; `list(queryset)` on big tables; `re.compile` per call (Python caches ~512, then thrashes); `json.dumps` of full model graphs; `pandas.read_*` per request holding frames in globals.
- Background workers: Celery tasks with `except Exception: pass`; `while True:` management commands with bare `except:`; Celery `worker_max_tasks_per_child` unset when tasks are known to leak (mitigation); Channels consumers that add to a module dict on `connect` and never remove on `disconnect`.

## What "good" looks like
```python
with open(path, "rb") as fh: data = fh.read()
with requests.Session() as s: ...          # or one module-level Session
client = httpx.AsyncClient(timeout=10)     # created once at startup, closed in lifespan shutdown

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache",
                      "OPTIONS": {"MAX_ENTRIES": 10000}, "TIMEOUT": 600}}

@shared_task(bind=True, max_retries=3)
def sync(self):
    try:
        do_sync()
    except Exception as exc:
        logger.exception("sync failed")
        raise self.retry(exc=exc)

@lru_cache(maxsize=1024)
def parse_rules(version: str): ...
```
Background tasks in ASGI: keep a reference (`self._tasks.add(task); task.add_done_callback(self._tasks.discard)`) and log exceptions in the callback.

## Manual trace checklist
1. Module-level mutable containers and class attributes: writers vs removers; is the key space bounded?
2. `apps.py ready()` and `signals.py`: every `connect()` runs once? `dispatch_uid` set?
3. Celery/RQ tasks and management-command loops: exceptions logged; per-iteration state discarded; `worker_max_tasks_per_child`/`--max-requests` present (note as mitigation, not fix).
4. External HTTP: one `Session`/`httpx.Client` per process; streamed responses closed.
5. File and temp-file handling: every `open`/`NamedTemporaryFile` inside `with` or `finally`; `delete=False` files removed.
6. `lru_cache`/`cache` decorators: on free functions with bounded args only; never on methods.
7. Django Channels: `connect` adds -> `disconnect` removes; `channel_layer.group_add` paired with `group_discard`.
8. ORM query logging in `DEBUG=True` (`connection.queries`) grows unbounded - confirm `DEBUG=False` in production; this is the most common "Django leaks" report.

## Stack-specific false positives
- `open()` immediately wrapped by `with` two lines later (grep hits the `open(` line).
- `lru_cache(maxsize=None)` on a function whose argument space is a small enum.
- `requests.Session()` at module scope - intended.
- Module-level `dict` used as a registry filled at import time only.
- Gunicorn `--max-requests` present: the leak is real but bounded; rate Medium and say the restart masks it.

## Tooling
- `tracemalloc`: `tracemalloc.start(25)` at boot (env-gated), snapshot before/after steady state, `snapshot2.compare_to(snapshot1, 'lineno')[:20]` - top growing allocation sites with file:line.
- `psutil.Process(pid).memory_info().rss` sampled every 15 s (or `ps -o rss= -p <pid>`), `len(psutil.Process(pid).open_files())`, `psutil.Process(pid).num_fds()`, `threading.active_count()`; `gc.get_count()`, `gc.collect()` before the final sample; `objgraph.show_growth()` between samples.
- `memray run --live gunicorn ...` or `memray run -o out.bin app.py` then `memray flamegraph out.bin` (Linux/macOS).
- `python -X dev` warns on unclosed files/sockets (`ResourceWarning`) - run the test suite with it once.
- Static analysis: `ruff` rule `SIM115` (open without context manager), `pylint` `consider-using-with` (R1732), `bandit` B310.

## References
CWE-401, CWE-404, CWE-772, CWE-770, CWE-390; Python docs `tracemalloc`, `functools.lru_cache` (note on methods); Django docs "Cache framework - Local-memory caching" (MAX_ENTRIES), "Signals - Preventing duplicate signals"; Celery docs `worker_max_tasks_per_child`; Gunicorn `--max-requests`.
