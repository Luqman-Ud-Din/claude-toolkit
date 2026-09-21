# Python / Django reference for audit-authz-and-access-control

## Stack markers
`manage.py`, `settings.py`, `urls.py`, `requirements.txt`/`pyproject.toml` with `django`/`djangorestframework`. Flask/FastAPI share this file's generic sections (decorators differ).

## Where the relevant code lives
`urls.py` (route table), `views.py`/`viewsets.py` (`permission_classes`, `get_queryset`), `serializers.py` (field exposure), `settings.py` (`REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']`), Celery tasks (`tasks.py`, no request identity).

## Dangerous / interesting APIs and patterns
- Missing auth: a DRF view with `permission_classes = [AllowAny]`, or no `permission_classes` when the project default is `AllowAny` (check `settings.py` - the default default is `AllowAny`). A plain Django view with no `@login_required`.
- IDOR: `Model.objects.get(pk=...)` / `filter(id=...)` not scoped to `request.user`. The idiomatic guard is overriding `get_queryset(self)` to `filter(owner=self.request.user)`, or `get_object_or_404(Model, pk=pk, owner=request.user)`.
- Mass assignment: `ModelSerializer` with `fields = '__all__'` (exposes `is_staff`, `is_superuser`, `role`), or `Model.objects.create(**request.data)`. Use an explicit `fields`/`read_only_fields` list.
- Role enforcement: `IsAdminUser`, custom `BasePermission.has_object_permission`, `@permission_required`. Template-level checks are not enforcement.

## What "good" looks like
```python
class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)   # object scope

class ProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["display_name", "email"]        # role/is_staff NOT bindable
```

## Manual trace checklist
1. Read `settings.py` `DEFAULT_PERMISSION_CLASSES` - it sets the baseline.
2. Every viewset - is `get_queryset` scoped to the user, or does it return `.all()`?
3. Every serializer - `__all__` or an explicit field list? Any writable privilege field?
4. Celery/management commands - do they carry and enforce tenant/user?

## Stack-specific false positives
`AllowAny` on registration/login/password-reset; `objects.get(pk=...)` inside a `get_queryset` already filtered to the user; `fields='__all__'` on a read-only serializer used only for admin responses.

## Tooling
`bandit -r .`, `semgrep --config p/django`, `python manage.py show_urls` (django-extensions) to list routes. Live probe: `scripts/authz_probe.py`.

## References
CWE-306, CWE-862, CWE-863, CWE-639, CWE-915, CWE-602. ASVS 4.1/4.2. OWASP A01:2021.
