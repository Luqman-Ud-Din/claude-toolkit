# Python / Django (and Flask, FastAPI) reference for audit-concurrency-and-race-condition

## Stack markers
`manage.py`, `requirements.txt`/`pyproject.toml` with `django`, `djangorestframework`, `flask`, `fastapi`. Variants: Django ORM vs SQLAlchemy; gunicorn/uvicorn workers (each process has its own memory; threads within a worker share it); Celery / RQ / Dramatiq tasks; Celery beat / APScheduler / django-crontab schedules; `ATOMIC_REQUESTS`.

## Where the relevant code lives
- Handlers: views/viewsets (`create`, `update`, `perform_create`), `@api_view(["POST"])`, FastAPI `@app.post`, webhook views (`@csrf_exempt`), Celery `@shared_task`.
- Data: `services.py`, `models.py` methods (`Model.objects.filter(...).exists()` then `create()`; `obj.balance -= x; obj.save()`), `transaction.atomic`, `select_for_update`, `F()` expressions, `update_or_create`/`get_or_create` (safe only with a unique constraint).
- Schema: `unique=True`, `UniqueConstraint`, `unique_together`, migrations; SQLAlchemy `UniqueConstraint`, `version_id_col`.
- Shared state: module-level dicts/lists, class attributes on views/services, `global`, `functools.lru_cache` on mutable results, `settings` mutated at runtime; Flask `g` misuse; FastAPI dependencies with mutable defaults.
- Jobs: `beat_schedule`, `@periodic_task`, APScheduler, management commands run by cron.

## Dangerous / interesting APIs and patterns
- Check-then-act: `if not User.objects.filter(email=e).exists(): User.objects.create(...)`; `acct = Account.objects.get(id=i); if acct.balance >= amt: acct.balance -= amt; acct.save()` (no `select_for_update`, no `F()`); `if order.status == "pending": order.status = "paid"; order.save()`.
- `get_or_create`/`update_or_create` on fields without a unique constraint (documented to race); `save()` after `get()` writes every field (lost update) unless `update_fields`.
- No unique constraint: `EmailField()` without `unique=True`; `unique_together` missing on (tenant, code).
- Idempotency: payment/refund/webhook views without an `Idempotency-Key` or event-id table; Celery tasks with `autoretry_for`/`retry()` that create side effects without a dedupe key; `acks_late=True` (at-least-once) with non-idempotent bodies; Stripe calls without `idempotency_key=`.
- Optimistic concurrency: no version field (`django-concurrency` `IntegerVersionField`, SQLAlchemy `version_id_col`); `Model.objects.filter(pk=pk).update(...)` without a status/version condition when one is needed.
- Transactions: multi-model writes outside `transaction.atomic()`; `ATOMIC_REQUESTS=False` and no explicit atomic; side effects (email, HTTP) inside `atomic` without `on_commit`; `select_for_update()` outside a transaction (raises) or on a queryset with `select_related` nullable joins (`of=`); SQLite in dev hiding lock behaviour.
- Shared state: module-level `_cache = {}` mutated in views; class-level `items = []` on a view/serializer (shared across requests within a worker thread pool); `global counter`; `lru_cache` returning mutable objects that views mutate.
- Collections: `dict`/`list`/`set` mutated from threads (gunicorn `--threads`, `ThreadPoolExecutor`) without `threading.Lock`; note the GIL does not make compound operations atomic.
- Jobs: Celery beat with more than one beat process (each schedules every task); periodic tasks without a lock (`cache.add(lock_key, ..., timeout)` / `redis.set(nx=True)` / `django-celery-beat` single scheduler); cron management commands on every server; APScheduler in every gunicorn worker.

## What "good" looks like
```python
class User(models.Model):
    class Meta: constraints = [models.UniqueConstraint(fields=["company", "email"], name="uq_user_company_email")]
try:
    with transaction.atomic(): User.objects.create(...)
except IntegrityError: raise Conflict("email exists")
# atomic conditional update
rows = Stock.objects.filter(pk=pk, qty__gte=q).update(qty=F("qty") - q)
if rows == 0: raise InsufficientStock()
# row lock inside a transaction
with transaction.atomic():
    acct = Account.objects.select_for_update().get(pk=pk)
    if acct.balance < amt: raise InsufficientFunds()
    acct.balance -= amt; acct.save(update_fields=["balance"])
# idempotency key stored first
if not IdempotencyKey.objects.try_insert(key, request.data): return Response(IdempotencyKey.objects.stored(key))
stripe.PaymentIntent.create(..., idempotency_key=key)
# periodic task lock
@shared_task
def expire_trials():
    if not cache.add("lock:expire_trials", "1", timeout=600): return
    try: ...
    finally: cache.delete("lock:expire_trials")
```

## Manual trace checklist
1. Every mutating view/task on money, stock, uniqueness: find the read and the write; `atomic` + `select_for_update`, `F()` conditional update, or version check present.
2. `grep -rn "\.exists()\|get_or_create\|update_or_create" --include=*.py` followed by `create(`/`save(`: constraints in `Meta` and migrations.
3. Module-level and class-level mutable state: `grep -rn "^\w\+ = \({}\|\[\]\|set()\|dict()\)" --include=*.py`, `global ` statements; worker/thread model in `gunicorn.conf.py`/Procfile.
4. Payment/webhook/task handlers: key or event-id dedupe; `acks_late`, `autoretry_for` with side effects; `idempotency_key=` on provider calls.
5. Version fields and `RecordModifiedError`/`StaleDataError` handling.
6. Celery beat/APScheduler/cron: single scheduler process; per-task lock; body idempotent per item.
7. `ATOMIC_REQUESTS`, `transaction.atomic` coverage, `on_commit` for side effects.

## Stack-specific false positives
- Module-level constants and settings read-only after import; `lru_cache` on pure functions returning immutables.
- `get_or_create` on a field that *has* a unique constraint (documented safe: it catches `IntegrityError` and retries the get).
- `select_for_update` inside `atomic` with the right rows locked.
- Single-worker, single-thread deployments documented as such (reduce memory-state findings to Low, not zero).

## Tooling
`grep -rn "unique=True\|UniqueConstraint\|unique_together" --include=models.py`; `python manage.py makemigrations --check --dry-run` (schema drift); `ruff` rule `B006` (mutable defaults); `pytest` with `TransactionTestCase` + threads to reproduce; `locust` two-user burst or `scripts/double_submit.sh`; `celery inspect scheduled` and count of beat processes.

## References
CWE-362, CWE-367, CWE-662, CWE-820; Django `select_for_update`, `F()` expressions, `get_or_create` race note; Celery "ensuring a task is only executed one at a time" cookbook; Stripe idempotent requests; ASVS 11.1.4.
