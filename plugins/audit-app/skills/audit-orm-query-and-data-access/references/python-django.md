# Python / Django ORM (also SQLAlchemy, Django REST Framework) reference for audit-orm-query-and-data-access

## Stack markers
`manage.py`, `django` in requirements; DRF (`djangorestframework`) for API views/serializers; `sqlalchemy` for Flask/FastAPI. Tracking is N/A in Django (no change tracker); the TRACKING class becomes "full model instances loaded where `values()`/`only()` would do" and, for SQLAlchemy, "session identity map growth in batch loops without `expunge`/`expire`".

## Where the relevant code lives
`models.py` (`Meta.indexes`, `db_index=True`, `related_name`), `views.py`/`viewsets.py`/`api/*.py`, `serializers.py` (nested serializers and `SerializerMethodField` are the classic N+1 site), `managers.py`/`querysets.py`, `admin.py` (`list_select_related`), `tasks.py`, `migrations/` (index history), `settings.py` (`REST_FRAMEWORK.DEFAULT_PAGINATION_CLASS`, `PAGE_SIZE`).

## Dangerous / interesting APIs and patterns
- NPLUS1: `for obj in qs: obj.related.field` or `obj.children.all()` with no `select_related`/`prefetch_related`; DRF nested serializers / `SerializerMethodField` that hit `obj.<fk>` or `obj.<m2m>.all()` per row; template loops (`{% for o in orders %}{{ o.customer.name }}`); `Model.objects.get(pk=x)` inside a loop; `.count()`/`.exists()` on a related manager per row.
- UNBOUNDED: `Model.objects.all()` / `.filter(...)` returned from a view/serializer with no slicing `[:n]` and no DRF pagination (`pagination_class = None` or `DEFAULT_PAGINATION_CLASS` unset); `list(qs)`; `serializer(qs, many=True).data` on an unpaged queryset; `queryset = Model.objects.all()` on a `ListAPIView` without pagination configured; exports with `.iterator()` absent.
- TRACKING/over-fetch: full instances where `.values('a','b')`/`.values_list(..., flat=True)`/`.only(...)`/`.defer(...)` would do; `len(qs)` (materialises) vs `qs.count()`; SQLAlchemy loops adding to a session without `session.expunge_all()`.
- INDEX: `.filter(company_id=..., status=...)`, `.order_by('-created_at')`, `.filter(name__icontains=...)` on fields lacking `db_index=True` / `Meta.indexes` / migrations `AddIndex`; `__icontains` with leading wildcard cannot use a btree index (needs trigram/GIN).
- TXN: two `.save()`/`.create()`/`.update()` on different models in one view/service without `transaction.atomic()`; `ATOMIC_REQUESTS` false (default) and no explicit atomic; `atomic()` opened but a Celery task enqueued inside it runs before commit (use `transaction.on_commit`); `select_for_update()` missing on read-modify-write of stock/balance rows (hand to `audit-concurrency-and-race-condition`).
- INEFFICIENT: `if qs.count() > 0:` / `if len(qs):` / `if qs:` on large sets (use `.exists()`); `.all()` then Python filtering (`[o for o in qs if o.status == 'x']`); `.filter().filter()` chains fine, but `qs.filter(...)[0]` vs `.first()`; `Model.objects.filter(...).delete()` in loops; `bulk_create`/`bulk_update` absent for batch writes; `.distinct()` on wide joins; `.annotate` with `Count` on prefetched relations (double work).

## What "good" looks like
```python
class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    pagination_class = StandardPagination            # PAGE_SIZE=20, max_page_size=100
    serializer_class = ProductListSerializer          # flat fields only
    def get_queryset(self):
        return (Product.objects.filter(company_id=self.request.user.company_id, deleted=False)
                .select_related("category")            # FK used by the serializer
                .prefetch_related("tags")              # M2M used by the serializer
                .only("id", "name", "price", "category__name")
                .order_by("name"))

with transaction.atomic():                            # sale + stock + ledger together
    sale = Sale.objects.create(...)
    StockMovement.objects.bulk_create(moves)
    Ledger.objects.create(...)
    transaction.on_commit(lambda: notify.delay(sale.id))

if Product.objects.filter(sku=sku).exists(): ...      # not count() > 0
```
Exports: `for row in qs.iterator(chunk_size=2000): writer.writerow(...)`. Settings: `REST_FRAMEWORK = {"DEFAULT_PAGINATION_CLASS": "...PageNumberPagination", "PAGE_SIZE": 20}`.

## Manual trace checklist
1. DRF views: `pagination_class` resolved (view, then settings default). Any `ListAPIView`/`list()` with `pagination_class = None` on a transactional model is UNBOUNDED.
2. Serializers used by list endpoints: every nested serializer / `SerializerMethodField` / `source='fk.field'` -> matching `select_related`/`prefetch_related` in `get_queryset`.
3. Views/services writing two models: `transaction.atomic()` present; `on_commit` for side effects.
4. `filter`/`order_by` fields on the top endpoints vs `models.py` indexes and migrations -> `audit-db-schema`.
5. Templates and admin: `list_select_related`, `raw_id_fields` for FK-heavy admin lists.
6. Exports/reports: `.iterator()` or chunked; `StreamingHttpResponse` for CSV.

## Stack-specific false positives
- `.all()` on reference tables (currencies, units) - bounded.
- `.count()` used for pagination totals - correct.
- `prefetch_related` + `for x in obj.related.all()` - uses the prefetch cache; only flag `.filter()`/`.count()` on the related manager (bypasses the cache).
- `len(qs)` after the queryset was already evaluated in the same function (uses the cache).
- Loops with `bulk_create`/`bulk_update` at the end - write side batched.

## Tooling
- Logging block in `references/query-logging.md` (`django.db.backends` logger, debug toolbar, `assertNumQueries`).
- `nplusone` package (`NPLUSONE_RAISE=True` in tests), `django-silk` (per-request query count and duplicates), `django-querycount` middleware.
- `python manage.py shell -c "from django.db import connection; ..."` with `reset_queries()` to count per call.
- `ruff`/`pylint-django` (no direct N+1 rule; use `django-silk` output instead); `sqlalchemy` `echo=True` + `selectinload`.

## References
CWE-1049, CWE-770, CWE-662; ASVS-12.1.1; Django docs "Database access optimization" (`select_related`, `prefetch_related`, `exists`, `iterator`, `bulk_create`), "Database transactions"; DRF "Pagination"; SQLAlchemy "Relationship Loading Techniques".
