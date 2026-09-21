# Python / Django (and Flask, FastAPI) reference for audit-business-logic

## Stack markers
`manage.py`, `requirements.txt`/`pyproject.toml` with `django`, `djangorestframework`, `flask`, `fastapi`. Variants: DRF serializers vs plain views; Celery/Django-Q/APScheduler jobs; `django-fsm` or `transitions` if used (explicit transition table: audit its content).

## Where the relevant code lives
- Business rules: `services.py`, `use_cases/`, `domain/`, model methods (`Order.pay()`), signal handlers (`signals.py`: side effects hide here), DRF `perform_create`/`perform_update`.
- State: `class Status(models.TextChoices)`, `order.status = ...`, `choices=`.
- Money: `DecimalField(max_digits, decimal_places)`, `decimal.Decimal`, `quantize`, `ROUND_HALF_UP`; `FloatField` is the smell.
- Entry points: `urls.py` -> views/viewsets; `@api_view`; webhook views (`csrf_exempt`); Celery `@shared_task`; management commands.
- Validation: serializer fields (`min_value`), `validate_<field>`, `validate()`, model `clean()`, Pydantic models (FastAPI).

## Dangerous / interesting APIs and patterns
- `FloatField` for price/amount/total/balance; `float(request.data['amount'])`; `round(x, 2)` (banker's rounding in Python 3) on money; `Decimal(0.1)` (from float) instead of `Decimal("0.1")`.
- `quantize` per line and again on the total, or never.
- `order.status = Status.PAID` in views; `if order.status == ...` chains repeated across views; no `can_transition`.
- `order.total -= discount` / `cart.total = cart.total - coupon.value` in a view or signal that fires repeatedly (`post_save` recomputing and mutating).
- `Serializer` with `fields = '__all__'` on Order/User (status, total, role, is_staff writable); `Model.objects.create(**request.data)`.
- `F('stock') - qty` without a `filter(stock__gte=qty)` guard; `select_for_update()` absent (hand to RACE).
- Webhook views without signature verification or event-id dedupe.
- `timezone.now().date()` / `datetime.now()` in cutoffs (hand to TIME).
- `transaction.atomic()` missing where status and stock/payment change together; `on_commit` side effects out of order.

## What "good" looks like
```python
class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"; PAID = "paid"; SHIPPED = "shipped"; CANCELLED = "cancelled"; REFUNDED = "refunded"
    TRANSITIONS = {Status.PENDING: {Status.PAID, Status.CANCELLED}, Status.PAID: {Status.SHIPPED, Status.REFUNDED},
                   Status.SHIPPED: set(), Status.CANCELLED: set(), Status.REFUNDED: set()}
    def transition(self, to):
        if to not in self.TRANSITIONS[self.status]:
            raise InvalidTransition(self.status, to)
        self.status = to

def compute_total(order, coupon=None) -> Decimal:
    subtotal = sum((l.unit_price * l.qty for l in order.lines.all()), Decimal("0"))
    discount = min(subtotal, coupon.value_for(subtotal)) if coupon else Decimal("0")
    return (subtotal - discount + tax(subtotal - discount)).quantize(Decimal("0.01"), ROUND_HALF_UP)
```
`OrderCoupon` model with `UniqueConstraint(fields=["order", "coupon"])`; serializers with explicit `fields = [...]` and `read_only_fields = ["status", "total"]`.

## Manual trace checklist
1. Payment confirm / webhook: amount source, `status` guard, `transaction.atomic`, signature check, dedupe by event id.
2. `grep -rn "\.status = " --include=*.py` and `signals.py`: map every status write, including ones in signals.
3. Pricing: single `compute_total`; can `apply_coupon` run twice; is `total` derived or mutated.
4. Stock: every `stock`/`quantity` write and its guard (hand the race to RACE).
5. Admin (`is_staff`, `IsAdminUser`) actions that force status/amount; `LogEntry`/audit present.
6. Serializers with `__all__` or writable `status`/`total`/`role`/`is_staff`.

## Stack-specific false positives
- `FloatField` for measurements, coordinates, weights, ML scores.
- `round()` on percentages for display, `quantize` in a serializer `to_representation`.
- `django-fsm` `@transition` decorators: the table is the good pattern; audit source/target lists.
- `status` comparison chains in a template filter or admin `list_display`.

## Tooling
`python manage.py check`; `grep -rn "FloatField" --include=models.py`; `ruff`/`flake8` with `flake8-bugbear`; inspect `DecimalField` precision in models; `pytest -k pricing` to see whether rounding is tested at all.

## References
CWE-840, CWE-841, CWE-682, CWE-915, ASVS 11.1.x, Python `decimal` module docs (rounding modes), Django `DecimalField` docs, `django-fsm` README.
