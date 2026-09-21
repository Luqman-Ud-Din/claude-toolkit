# .NET / C# reference for audit-business-logic

## Stack markers
`*.csproj`, `*.sln`, `Program.cs`. Variants: ASP.NET Core controllers vs minimal APIs; EF Core; Hangfire/Quartz jobs; MediatR handlers; Ocelot/YARP gateway in front (routes there are not logic).

## Where the relevant code lives
- Business rules: `*Manager.cs`, `*Service.cs`, `*Handler.cs` (MediatR), `Domain/` aggregates, `Application/UseCases/`.
- State: `enum *Status`, `enum *State` in `*.Entity`/`Domain`; assignments `entity.Status =`.
- Money: `decimal` properties on `Order`, `Invoice`, `Payment`, `Voucher`, `Ledger`; `Math.Round`, `decimal.Round`, `ToString("F2")`.
- Entry points: `Controllers/*Controller.cs`, `BackgroundJobs/*`, webhook controllers (`[AllowAnonymous]` + signature).
- Validation: DataAnnotations on `HostModel`/DTO classes, FluentValidation `AbstractValidator<T>`, `ModelState`.

## Dangerous / interesting APIs and patterns
- `double`/`float` on any property named Amount, Price, Total, Cost, Balance, Rate, Tax, Discount; `(double)` casts in pricing; `Convert.ToDouble`.
- `Math.Round(x)` without `MidpointRounding` (banker's rounding by default in .NET, often not what invoices expect); `Math.Round` inside a loop per line and again on the total.
- `switch (order.Status)` / `if (status == ...)` chains scattered across controllers instead of one transition table.
- `entity.Status = Status.X` in controllers (logic leaked to the edge); `Total -= discount`, `Total += line` in methods called from multiple places.
- Request DTOs containing `Total`, `Price`, `Discount`, `Status`, `Role`, `CompanyId` that AutoMapper copies straight into the entity (`CreateMap<OrderDto, Order>()` without `.Ignore()`).
- `[AllowAnonymous]` webhook handlers that update payment state; `HttpContext.User` never consulted in "admin" flows.
- Hangfire `RecurringJob.AddOrUpdate` bodies that mutate orders/subscriptions (hand overlap to RACE).
- `DateTime.Now` in cutoffs/expiry (hand to TIME).

## What "good" looks like
```csharp
public static class OrderTransitions {
    static readonly Dictionary<OrderStatus, OrderStatus[]> Allowed = new() {
        [OrderStatus.Pending]   = new[] { OrderStatus.Paid, OrderStatus.Cancelled },
        [OrderStatus.Paid]      = new[] { OrderStatus.Shipped, OrderStatus.Refunded },
        [OrderStatus.Shipped]   = new[] { OrderStatus.Completed, OrderStatus.Returned },
    };
    public static void Ensure(OrderStatus from, OrderStatus to) {
        if (!Allowed.TryGetValue(from, out var next) || !next.Contains(to))
            throw new InvalidOperationException($"Cannot move order from {from} to {to}");
    }
}
// pricing: derive, never mutate
decimal subtotal = order.Lines.Sum(l => l.UnitPrice * l.Quantity);
decimal discount = coupon is null ? 0m : Math.Min(subtotal, coupon.ValueFor(subtotal));
order.Total = decimal.Round(subtotal - discount + Tax(subtotal - discount), 2, MidpointRounding.AwayFromZero);
```
Money as `decimal` with SQL `decimal(18,4)`; one rounding at the end; coupons recorded in an `OrderCoupon` row with a unique index on (OrderId, CouponId).

## Manual trace checklist
1. Payment confirm/webhook: where does the amount come from; is the previous status checked; what happens on gateway failure.
2. Order status: list every `Status =` write (`grep -rn "Status = " --include=*.cs`) and map each to the diagram.
3. Pricing/discount: is the total recomputed from lines or mutated; can `ApplyDiscount` run twice.
4. Stock: every `Quantity`/`Stock` write goes through a ledger/manager; negative guard present (hand the race to RACE).
5. Admin overrides and impersonation: `[Authorize(Roles = "SuperAdmin")]` actions that set status/amount; is a reason logged.
6. AutoMapper profiles: request -> entity maps that include Status/Total/Role.

## Stack-specific false positives
- `double` used for weights, dimensions, percentages that are not stored money; `float` in ImageSharp/reporting code.
- `Math.Round` on display-only values in a report/export.
- `switch (status)` used only to pick a label or colour (read-only), not to transition.
- Enum `Status` writes inside a single `StateMachine`/`Transitions` class: that is the good pattern.

## Tooling
Roslyn analyzer `CA1305` (culture in ToString of money); `grep -rn "double\|float" --include=*.cs | grep -i "amount\|price\|total"`; EF model: `grep -rn "HasColumnType(\"decimal"` to confirm precision; `grep -rn "CreateMap<" --include=*.cs` to list request-to-entity maps.

## References
CWE-840, CWE-841, CWE-682, CWE-20, CWE-915 (mass assignment of Status/Total), ASVS 11.1.1-11.1.8 (business logic), OWASP Business Logic cheat sheet.
