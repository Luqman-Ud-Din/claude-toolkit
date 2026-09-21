# Java / Spring reference for audit-concurrency-and-race-condition

## Stack markers
`pom.xml` / `build.gradle` with `spring-boot-starter-*`. Variants: JPA/Hibernate vs JDBC/jOOQ; `@Scheduled` vs Quartz vs Spring Batch; Kafka/RabbitMQ listeners; multiple instances behind a load balancer; ShedLock / Redisson present or not.

## Where the relevant code lives
- Handlers: `@RestController` methods with `@PostMapping`/`@PutMapping`/`@DeleteMapping`; `@KafkaListener`/`@RabbitListener`/`@SqsListener` consumers; webhook controllers.
- Services: `@Service` methods with/without `@Transactional`; repositories (`existsBy...`, `findBy...` then `save`).
- Schema: `@Table(uniqueConstraints=...)`, `@Column(unique=true)`, `@Version`, Flyway/Liquibase migrations (`UNIQUE`, `version` columns).
- Shared state: `static` fields, singleton `@Component`/`@Service` fields (all Spring beans are singletons by default), `@Async` methods touching bean fields, `ThreadLocal` without cleanup.
- Jobs: `@Scheduled`, `@EnableScheduling`, Quartz `JobDetail`, `@SchedulerLock`.

## Dangerous / interesting APIs and patterns
- Check-then-act: `if (!repo.existsByEmail(e)) repo.save(u)`; `Account a = repo.findById(id); if (a.getBalance() >= amt) { a.setBalance(...); repo.save(a); }` without `@Lock` or `@Version`; `if (order.getStatus() == PENDING) order.setStatus(PAID)` with no conditional update.
- No unique constraint behind an `existsBy` check (`@Column(unique = true)` absent, no `UNIQUE` in migrations).
- Idempotency: payment/refund/webhook endpoints without an `Idempotency-Key` header or an event-id table; `@Retryable`/`RetryTemplate`/Resilience4j `@Retry` on methods that create side effects; listeners with `AckMode.MANUAL` never deduping message ids.
- Optimistic concurrency: no `@Version` on entities edited by multiple users/jobs; `OptimisticLockException`/`ObjectOptimisticLockingFailureException` not caught; `@Modifying @Query("update ...")` without a version/status condition.
- Transactions: `@Transactional` missing on multi-repository writes; `@Transactional` on a `private` or same-class-called method (proxy bypass, no transaction); `propagation = REQUIRES_NEW` splitting an atomic pair; isolation left at default with a read-modify-write.
- Shared state: `private Map<...> cache = new HashMap<>()` in a singleton bean; `static int counter`; `SimpleDateFormat` field (not thread-safe); `List`/`ArrayList` fields appended in request methods; `@Async` writing bean fields.
- Collections: `HashMap`, `ArrayList`, `HashSet` shared without `synchronized`/`ConcurrentHashMap`/`CopyOnWriteArrayList`; `Collections.synchronizedMap` with compound operations (`if (!containsKey) put`).
- Jobs: `@Scheduled` without `@SchedulerLock` (ShedLock) or Quartz clustered store when instances > 1; `fixedDelay` assumed to prevent cross-instance overlap; Spring Batch job without a unique `JobParameters` guard.

## What "good" looks like
```java
@Entity @Table(uniqueConstraints = @UniqueConstraint(columnNames = {"company_id", "email"}))
class User { @Version private long version; }
try { repo.saveAndFlush(user); } catch (DataIntegrityViolationException e) { throw new ConflictException("email exists"); }
// atomic conditional update
@Modifying @Query("update Stock s set s.qty = s.qty - :q where s.id = :id and s.qty >= :q") int reserve(@Param("id") long id, @Param("q") int q);
if (repo.reserve(id, q) == 0) throw new InsufficientStockException();
// pessimistic lock inside one transaction
@Lock(LockModeType.PESSIMISTIC_WRITE) Optional<Account> findWithLockById(Long id);
@Transactional public void debit(...) { var a = repo.findWithLockById(id).orElseThrow(); ... }
// idempotency
@PostMapping("/charge") ResponseEntity<?> charge(@RequestHeader("Idempotency-Key") String key, ...) { if (!keys.tryInsert(key)) return keys.storedResponse(key); ... }
// jobs
@Scheduled(cron = "...") @SchedulerLock(name = "expireTrials", lockAtMostFor = "10m") public void expireTrials() { ... }
// shared state
private final ConcurrentMap<String, AtomicInteger> hits = new ConcurrentHashMap<>();
```

## Manual trace checklist
1. Every mutating endpoint/consumer on money, stock, uniqueness: locate read and write; find `@Transactional`, `@Lock`, `@Version`, or conditional `@Modifying` query.
2. `grep -rn "existsBy\|findBy.*isPresent\|count.*== 0" --include=*.java` followed by `save(`: check constraints in entities/migrations.
3. `grep -rn "static [^f]" --include=*.java | grep -v "final\|class\|void\|static <"` and singleton bean fields that are collections or counters: who writes them.
4. Payment/webhook/listener handlers: key or event-id dedupe; retry annotations on side-effecting methods.
5. `@Version` presence and `OptimisticLock*` handling.
6. `@Scheduled`/Quartz: ShedLock or clustered store; instance count; idempotent body.
7. `@Transactional` self-invocation and `private` methods (no proxy).

## Stack-specific false positives
- `static final` immutable constants, `Logger`, `ObjectMapper` (thread-safe), `RestTemplate`/`WebClient`.
- `ConcurrentHashMap` with `computeIfAbsent`/`merge` (atomic); `AtomicInteger`/`LongAdder`.
- `existsBy` pre-check *plus* a unique constraint with `DataIntegrityViolationException` handled.
- `@Scheduled` with ShedLock, or a documented single-instance scheduler profile.
- `ThreadLocal` cleared in a `finally`/filter.

## Tooling
Error Prone / SpotBugs (`IS2_INCONSISTENT_SYNC`, `STCAL_*` for SimpleDateFormat, `AT_OPERATION_SEQUENCE_ON_CONCURRENT_ABSTRACTION`); `grep -rn "@Version\|@Lock\|@SchedulerLock\|Idempotency" --include=*.java`; `mvn dependency:tree | grep -i "shedlock\|redisson"`; JMeter/Gatling two-request burst; `scripts/double_submit.sh`.

## References
CWE-362, CWE-367, CWE-662, CWE-820; Spring Data JPA locking docs; ShedLock README; Hibernate optimistic locking; Stripe idempotent requests; ASVS 11.1.4.
