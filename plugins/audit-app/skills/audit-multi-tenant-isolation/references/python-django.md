# Python / Django reference for audit-multi-tenant-isolation

## Stack markers
`manage.py`, `settings.py`, DRF. Tenancy via `django-tenants`/`django-tenant-schemas` (schema-per-tenant), a tenant-aware default manager, or an explicit `tenant` FK filtered in `get_queryset`. Flask/FastAPI reuse the generic sections.

## Where the relevant code lives
`models.py` (managers), `views.py`/`viewsets.py` (`get_queryset`), `serializers.py`, `settings.py` (`DATABASE_ROUTERS`, middleware), `tasks.py` (Celery), management commands, cache config, storage backends.

## Dangerous / interesting APIs and patterns
- `.raw(...)`, `cursor.execute(...)`, `RawSQL(...)` - bypass managers and (in schema-per-tenant) may hit the wrong schema; must scope by tenant.
- `Model.objects.all()` / `objects.get(pk=...)` when the default manager is NOT tenant-aware - returns/loads across tenants.
- Tenant id from `request.data`/`request.query_params`/header trusted directly, instead of `request.tenant`/`request.user.tenant`.
- Celery tasks and management commands run outside the request/tenant middleware; with `django-tenants` the schema must be activated (`schema_context(tenant)`), else the task hits the public schema or a stale one.
- Cache keys without tenant (Django's cache is global unless `KEY_FUNCTION`/prefix adds the tenant); `default_storage` paths without a tenant prefix.

## What "good" looks like
```python
class InvoiceViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        return Invoice.objects.filter(tenant=self.request.tenant)
    def perform_create(self, s):
        s.save(tenant=self.request.tenant)      # never request.data['tenant']

@shared_task
def bill(tenant_id):
    with schema_context(tenant_id):             # activate the tenant schema
        ...
cache.set(f"tenant:{tenant.id}:invoice:{id}", val)
```

## Manual trace checklist
1. Read `settings.py` for the tenant middleware / DATABASE_ROUTERS and confirm the default manager is tenant-aware.
2. Every `.raw`/`objects.all`/`objects.get(pk=)` - tenant scope present?
3. Serializers do not accept a writable `tenant` field.
4. Celery tasks / commands activate the tenant schema or filter by tenant.
5. Cache prefix and storage paths include the tenant.

## Stack-specific false positives
Schema-per-tenant (`django-tenants`) makes an explicit `tenant=` filter unnecessary within an activated schema - confirm the schema is activated; admin/reporting across tenants that is authorized; `objects.get(pk=)` inside an already tenant-filtered `get_queryset`.

## Tooling
`bandit`, `semgrep --config p/django`, `scripts/data_access_paths.py`, `scripts/tenant_probe.py`.

## References
CWE-284, CWE-639, CWE-524, CWE-668. ASVS 4.1/4.2, 8.1. OWASP A01:2021.
