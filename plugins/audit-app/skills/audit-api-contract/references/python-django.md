# Python / Django (and Flask, FastAPI) reference for audit-api-contract

## Stack markers
`manage.py`, `requirements.txt`/`pyproject.toml` with `django`, `djangorestframework`, `flask`, `fastapi`. Variants: DRF with `drf-spectacular` / `drf-yasg`; FastAPI (built-in `/docs`, `/redoc`, `/openapi.json`); Flask with `flask-smorest`/`flasgger`/`connexion`; Django Ninja.

## Where the relevant code lives
- Spec: `urls.py` (`SpectacularAPIView`, `SpectacularSwaggerView`, `get_schema_view`), `settings.py` (`SPECTACULAR_SETTINGS`, `SERVE_PERMISSIONS`, `SERVE_INCLUDE_SCHEMA`), FastAPI `FastAPI(docs_url=..., openapi_url=...)`, `flask-smorest` `OPENAPI_*` config.
- Routes: `urls.py` (`path("api/v1/", include(...))`, `router.register`), DRF `ViewSet`/`APIView`, FastAPI `@app.get`/`APIRouter(prefix="/v1")`, Flask `Blueprint(url_prefix=...)`.
- DTOs: DRF serializers (`fields`, `read_only_fields`, `write_only=True`, `validate_*`), Pydantic models (`Field(..., ge=0, max_length=32)`, `model_config = ConfigDict(extra="forbid")`), marshmallow schemas (`unknown = RAISE`).
- Errors: DRF `EXCEPTION_HANDLER`, FastAPI `exception_handler(RequestValidationError)`, Flask `errorhandler`; `DEBUG` in prod.
- Pagination: `DEFAULT_PAGINATION_CLASS`, `PAGE_SIZE`, `max_page_size`, `LimitOffsetPagination`, FastAPI `Query(le=100)`, `fastapi-pagination`.
- Serialisation: `ModelSerializer` `fields = "__all__"`, `exclude`, `depth`; Pydantic `from_attributes`, `response_model`, `response_model_exclude`; Flask `jsonify(model.__dict__)`.

## Dangerous / interesting APIs and patterns
- Spec exposure: `SpectacularSwaggerView` in `urls.py` with `permission_classes = [AllowAny]` (or `SERVE_PERMISSIONS` unset = AllowAny) in prod; FastAPI `docs_url` not `None` in production settings; `flasgger` at `/apidocs` unauthenticated.
- Entity returned: `ModelSerializer` with `fields = "__all__"` on `User`/`Account`/`Order` (exposes `password`, `is_superuser`, `is_staff`, `api_key`, `tenant_id`); `depth = 1+` pulling relations; FastAPI endpoints without `response_model` returning ORM objects/dicts; `model_to_dict(user)`; Flask `jsonify(row._asdict())`; `serializers.serialize("json", queryset)`.
- Unpaginated: `ListAPIView` with `pagination_class = None`; `DEFAULT_PAGINATION_CLASS` unset; `@api_view` returning `Model.objects.all()`; FastAPI `limit: int = 100` without `le=`; `PAGE_SIZE` set but `max_page_size` unset on `PageNumberPagination` subclass with `page_size_query_param`.
- Validation: `request.data["x"]` used without a serializer; `serializer.is_valid()` without `raise_exception=True` and the result ignored; Pydantic models with no constraints; `extra="allow"`; `Serializer` allowing writes to `status`/`role`/`is_staff` (no `read_only_fields`).
- Error shape: `Response({"error": ...}, status=400)` in one view and DRF default `{"detail": ...}` or `{"field": [...]}` in another; FastAPI default `{"detail": [...]}` mixed with custom `{"message"}`; Flask `return {"msg": ...}, 400`; `DEBUG=True` tracebacks; `str(exc)` in responses.
- Status codes: `Response(data)` (200) on create instead of `status=201`; `200` on delete; `403` for unauthenticated (DRF returns 403 when no authenticator supports `WWW-Authenticate`); `get()` raising `DoesNotExist` -> 500; `ValueError` -> 500.
- Naming/dates: snake_case JSON (fine if consistent) mixed with camelCase from a renamer; `DATETIME_FORMAT` custom (`%d/%m/%Y`); naive datetimes serialised without offset (`USE_TZ=False`); `Decimal` as string vs float (`COERCE_DECIMAL_TO_STRING`) inconsistently.
- Versioning: `DEFAULT_VERSIONING_CLASS` unset; routes `api/` and `api/v2/` both live; `URLPathVersioning` declared but `ALLOWED_VERSIONS` open.

## What "good" looks like
```python
# settings.py
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "core.pagination.StandardPagination",  # PageNumberPagination, page_size=20, max_page_size=100
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning", "ALLOWED_VERSIONS": ["v1"],
    "EXCEPTION_HANDLER": "core.errors.problem_details_handler",         # RFC 9457 for every error
}
SPECTACULAR_SETTINGS = {"SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"], "SERVE_INCLUDE_SCHEMA": False}
# serializers.py
class UserSerializer(serializers.ModelSerializer):
    class Meta: model = User; fields = ["id", "email", "display_name", "role"]; read_only_fields = ["id", "role"]
class CreateOrderSerializer(serializers.Serializer):
    lines = LineSerializer(many=True, allow_empty=False); coupon_code = serializers.CharField(max_length=32, required=False)
# views.py
class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    def create(self, request, *a, **kw):
        s = CreateOrderSerializer(data=request.data); s.is_valid(raise_exception=True)
        return Response(OrderSerializer(service.create(**s.validated_data)).data, status=201)
# FastAPI
app = FastAPI(docs_url=None if settings.ENV == "prod" else "/docs", openapi_url=None if settings.ENV == "prod" else "/openapi.json")
@router.get("/orders", response_model=Page[OrderOut]) def list_orders(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)): ...
class CreateOrder(BaseModel): model_config = ConfigDict(extra="forbid"); lines: list[Line] = Field(min_length=1)
```

## Manual trace checklist
1. Spec views/`docs_url` and their permissions in the prod settings module.
2. Endpoint table: list views without pagination; serializers with `__all__`/`depth`; FastAPI routes without `response_model`.
3. Every write endpoint: serializer/Pydantic model used with `raise_exception`/validation; `read_only_fields` protect status/role; `extra="forbid"`.
4. Collect every `Response({...}, status=4xx)`/`HTTPException(detail=...)`/`return {...}, 4xx` shape; `EXCEPTION_HANDLER` presence.
5. `DEBUG`, `COERCE_DECIMAL_TO_STRING`, `DATETIME_FORMAT`, versioning settings.
6. Spec diff: previous schema from git/CI (`manage.py spectacular --file schema.yml`, or `/openapi.json` from a dev run) vs current via `scripts/spec_diff.py` (YAML needs PyYAML).

## Stack-specific false positives
- `fields = "__all__"` on a model with no sensitive or relational fields (recommend explicit list, Info).
- DRF default error shape if it is the only shape and `DEBUG=False`.
- `/docs` enabled in prod behind an authenticated gateway or `IsAdminUser` (record the control).
- `pagination_class = None` on an endpoint that returns a bounded reference list (e.g. 10 statuses) - confirm bound.

## Tooling
`python manage.py spectacular --file audit/evidence/audit-api-contract/schema.yml --validate`; `grep -rn "__all__\|depth = " --include=serializers.py`; `grep -rn "pagination_class = None\|docs_url" --include=*.py`; `$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py`; `pip install pyyaml` then `scripts/spec_diff.py old.yml new.yml`; `oasdiff` if installed.

## References
ASVS 13.1/13.2, OWASP API Security Top 10 2023, RFC 9457, DRF pagination/versioning/exception docs, drf-spectacular settings, FastAPI `response_model` and docs URL settings.
