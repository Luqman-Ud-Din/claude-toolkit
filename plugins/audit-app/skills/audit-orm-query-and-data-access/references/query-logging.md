# Query logging config per ORM (verify under load)

Turn this on in a staging environment, replay one request per suspect endpoint,
and count: queries per request, rows per query, and duration. Then run the
`audit-performance-and-scalability` load plan with logging on for 5 minutes and
grep the log. Never leave verbose query logging on in production - it is itself
a performance and PII risk (parameters are logged).

Pass criteria used by this skill:
- <= 10 queries per request on list/detail endpoints (1 + includes is the target).
- No query returns > 1000 rows unless it is an export that streams.
- No query on a list page > 200 ms at staging data volume.

## EF Core (.NET)
```csharp
// Program.cs - staging only
builder.Services.AddDbContext<AppDbContext>(o => o
    .UseSqlServer(cs)
    .EnableSensitiveDataLogging()            // parameters in the log; staging only
    .EnableDetailedErrors()
    .LogTo(Console.WriteLine, new[] { DbLoggerCategory.Database.Command.Name }, LogLevel.Information)
    .ConfigureWarnings(w => w.Throw(RelationalEventId.MultipleCollectionIncludeWarning)   // cartesian explosion
                              .Log(CoreEventId.FirstWithoutOrderByAndFilterWarning)));
```
or `appsettings.Staging.json`: `"Logging": { "LogLevel": { "Microsoft.EntityFrameworkCore.Database.Command": "Information" } }`.
Count: lines containing `Executed DbCommand` per request id (Serilog: enrich with `RequestId`); `(123ms)` prefix is the duration. Add `.TagWith("ProductsController.GetAll")` to suspect queries so they are greppable. Also `dotnet-counters ... --counters Microsoft.EntityFrameworkCore[active-db-contexts,total-queries,queries-per-second]`.

## Hibernate / JPA (Spring Boot)
```yaml
# application-staging.yml
spring:
  jpa:
    properties:
      hibernate:
        generate_statistics: true          # logs session metrics: "n JDBC statements executed"
        format_sql: true
logging:
  level:
    org.hibernate.SQL: DEBUG                 # each statement
    org.hibernate.orm.jdbc.bind: TRACE       # parameters (Hibernate 6); org.hibernate.type.descriptor.sql.BasicBinder for 5.x
    org.hibernate.stat: DEBUG                # per-session statistics incl. query count
```
Count: `Session Metrics` block per request (`nanoseconds spent executing N JDBC statements`). For hard limits in tests, add `spring.jpa.properties.hibernate.query.fail_on_pagination_over_collection_fetch=true` and consider `p6spy`/`datasource-proxy` with `QueryCountHolder` to assert counts per test.

## Prisma (Node)
```ts
const prisma = new PrismaClient({ log: [{ emit: 'event', level: 'query' }] });
prisma.$on('query', e => logger.info({ q: e.query, params: e.params, ms: e.duration, reqId: als.getStore()?.reqId }));
// or env: DEBUG="prisma:query" node dist/main.js
```
Count: query events per `reqId` (use `AsyncLocalStorage` to tag). Prisma `findMany` with no `take` is the unbounded shape; `include` on relations is one extra query per relation (batched, not per row) - N+1 in Prisma comes from `await` inside `for` loops.

## TypeORM (Node)
```ts
new DataSource({ ..., logging: ['query', 'slow'], maxQueryExecutionTime: 200, logger: 'advanced-console' });
```
Count: `query:` lines per request; `slow` lines are > 200 ms. Relations with `eager: true` on entities are hidden joins - check entity metadata.

## Sequelize (Node)
```ts
new Sequelize(url, { logging: (sql, timing) => logger.info({ sql, ms: timing }), benchmark: true });
```
Count: lines per request. `findAll()` with no `limit` is the unbounded shape; N+1 from `for (const x of rows) await x.getChildren()`.

## Mongoose (Node)
```ts
mongoose.set('debug', (coll, method, query, doc, opts) => logger.info({ coll, method, query }));
```
Count: `find`/`findOne` per request; `.populate()` is one extra query per path (batched). `find()` with no `.limit()` is unbounded.

## Django ORM (Python)
```python
# settings_staging.py
LOGGING = {"version": 1, "handlers": {"console": {"class": "logging.StreamHandler"}},
           "loggers": {"django.db.backends": {"handlers": ["console"], "level": "DEBUG"}}}   # needs DEBUG=True or a custom handler
```
Better: `django-debug-toolbar` (SQL panel shows count + duplicates), `nplusone` package (`NPLUSONE_RAISE = True` in tests), or in tests `with self.assertNumQueries(3): ...`. In code: `from django.db import connection, reset_queries; reset_queries(); ...; len(connection.queries)`.
Count: queries per request in the toolbar; "similar queries" count is the N+1 signal. `.all()`/`.filter()` without slicing is unbounded when serialised.

## SQLAlchemy (Python, if present)
`create_engine(url, echo=True)` or `logging.getLogger('sqlalchemy.engine').setLevel(logging.INFO)`; `selectinload`/`joinedload` for N+1; `.limit()` for bounds.

## What to record in the report
For each suspect endpoint: queries per request before/after, largest row count, slowest query; paste as the "Query-per-request estimates" table with the measured column filled in.
