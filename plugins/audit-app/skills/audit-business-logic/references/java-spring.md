# Java / Spring reference for audit-business-logic

## Stack markers
`pom.xml` / `build.gradle` with `spring-boot-starter-*`. Variants: Spring MVC controllers vs WebFlux; JPA/Hibernate; Spring Batch / `@Scheduled` jobs; Spring State Machine (if used, the transition table is explicit: audit its config).

## Where the relevant code lives
- Business rules: `*Service.java` (`@Service`, `@Transactional`), `domain/`, `usecase/`, `*Handler` for events/commands.
- State: `enum OrderStatus`, `entity.setStatus(...)`, `@Enumerated(EnumType.STRING)`.
- Money: `BigDecimal` fields; `setScale`, `RoundingMode`; `javax.money`/`org.javamoney` if present.
- Entry points: `@RestController`, `@PostMapping`, `@KafkaListener`, `@RabbitListener`, `@Scheduled`, webhook controllers.
- Validation: `@Valid` + Bean Validation (`@NotNull`, `@Min`, `@Positive`), custom `ConstraintValidator`.

## Dangerous / interesting APIs and patterns
- `double`/`float`/`Double` fields named amount, price, total, balance, rate, tax; `new BigDecimal(double)` (inexact) instead of `BigDecimal.valueOf` or the String constructor.
- `BigDecimal` arithmetic without `setScale(2, RoundingMode.HALF_UP)` at the end, or `setScale` per line and again on the total; `RoundingMode.HALF_EVEN` unintended.
- `Math.round(amount * 100) / 100.0`.
- `switch (order.getStatus())` in controllers; `setStatus(...)` called from more than one service; no `canTransition` helper.
- `total = total.subtract(discount)` in a method called on every cart update; `subtotal.add(...)` accumulators on the entity.
- Request DTO == entity (`@RequestBody Order order` then `repository.save(order)`): status/total/role assignable from the client.
- `@Transactional` missing on methods that write status and stock together; `@Transactional(readOnly = true)` on a mutating method.
- `@Scheduled` methods that mutate subscriptions/orders with no `ShedLock`/`@SchedulerLock` (hand overlap to RACE).
- `LocalDateTime.now()` in cutoff logic (hand to TIME).

## What "good" looks like
```java
public enum OrderStatus {
    PENDING(Set.of("PAID", "CANCELLED")), PAID(Set.of("SHIPPED", "REFUNDED")),
    SHIPPED(Set.of("COMPLETED", "RETURNED")), CANCELLED(Set.of()), COMPLETED(Set.of()), REFUNDED(Set.of()), RETURNED(Set.of());
    private final Set<String> next;
    OrderStatus(Set<String> next) { this.next = next; }
    public boolean canMoveTo(OrderStatus to) { return next.contains(to.name()); }
}
// in service
if (!order.getStatus().canMoveTo(PAID)) throw new IllegalStateException("...");
BigDecimal subtotal = lines.stream().map(l -> l.unitPrice().multiply(BigDecimal.valueOf(l.qty()))).reduce(ZERO, BigDecimal::add);
BigDecimal total = subtotal.subtract(discountFor(subtotal, coupon)).setScale(2, RoundingMode.HALF_UP);
```
Coupons recorded in an `order_coupon` table with a unique constraint; totals derived on read or recomputed in one `PricingService`.

## Manual trace checklist
1. Payment confirm and provider webhook: amount source, previous-status guard, failure path, `@Transactional` boundary.
2. `grep -rn "setStatus(" --include=*.java`: map each write to the diagram; find writes outside the owning service.
3. Pricing: is `PricingService` the single place; can `applyCoupon` run twice; is `order_coupon` unique.
4. Stock: `setQuantity`/`decrement` paths, negative guard; `@Version` or `SELECT ... FOR UPDATE` present (hand to RACE).
5. Admin overrides: `@PreAuthorize("hasRole('ADMIN')")` methods that set status/amount; audit trail (`@EntityListeners(AuditingEntityListener.class)`).
6. Mass assignment: controllers binding `@RequestBody` directly to entities.

## Stack-specific false positives
- `double` in analytics, geo, or weight fields; `Double` in `@Query` projections for reporting.
- `setScale` on display values in a mapper/DTO layer.
- Spring State Machine `StateMachineConfigurerAdapter`: the transition table is the good pattern; audit its content, not its existence.
- `setStatus` inside a single `OrderStateService` or the aggregate root.

## Tooling
Error Prone / SpotBugs (`FE_FLOATING_POINT_EQUALITY`, `DMI_BIGDECIMAL_CONSTRUCTED_FROM_DOUBLE`); `grep -rn "new BigDecimal(" --include=*.java | grep -v '"'`; ArchUnit rules to assert `setStatus` is only called from the service package; `mvn dependency:tree | grep money`.

## References
CWE-840, CWE-841, CWE-682, CWE-915, ASVS 11.1.x, Spring Data JPA `@Transactional` docs, `java.math.RoundingMode` javadoc.
