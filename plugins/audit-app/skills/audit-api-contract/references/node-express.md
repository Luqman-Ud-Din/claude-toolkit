# Node / Express (and NestJS, Fastify, Koa) reference for audit-api-contract

## Stack markers
`package.json` with `express`, `@nestjs/core`, `fastify`, `koa`. Variants: spec from `swagger-jsdoc`/`swagger-ui-express`, `@nestjs/swagger` (`SwaggerModule.setup`), `@fastify/swagger`, `express-openapi-validator`, tsoa, or hand-written `openapi.yaml`; validation via zod/joi/yup/celebrate/`class-validator`; ORM (Prisma, TypeORM, Sequelize, Mongoose) for entity leakage.

## Where the relevant code lives
- Spec: `src/main.ts` (`SwaggerModule.setup('api', app, doc)`), `app.use('/api-docs', swaggerUi.serve, ...)`, `openapi.yaml`/`swagger.json` in repo, `@fastify/swagger-ui` registration.
- Routes: `routes/*.ts` (`router.get('/orders', ...)`), `app.use('/api/v1', router)`, NestJS `@Controller('orders')` + `@Version('1')` (`app.enableVersioning`), Fastify `fastify.register(routes, { prefix: '/v1' })`.
- DTOs: `dto/*.dto.ts` (`class-validator` decorators, `ValidationPipe({ whitelist: true, forbidNonWhitelisted: true })`), zod schemas (`.strict()`), joi (`celebrate`), Fastify JSON schema (`additionalProperties: false`).
- Errors: global error middleware `(err, req, res, next)`, NestJS `HttpException`/exception filters, Fastify `setErrorHandler`; `res.status(...).json({...})` per route.
- Pagination: `limit`/`offset`/`page` parsing, `take`/`skip`, `findAndCountAll`, Mongoose `.limit()`.
- Serialisation: `class-transformer` `@Exclude()`/`@Expose()`, `ClassSerializerInterceptor`, Mongoose `toJSON` transform / `select: false`, Prisma `select`/`omit`, Sequelize `attributes: { exclude }`, `toJSON()` overrides.

## Dangerous / interesting APIs and patterns
- Spec exposure: `swaggerUi.serve` / `SwaggerModule.setup` mounted regardless of `NODE_ENV`; no auth middleware in front; spec served from `public/`.
- Entity returned: `res.json(await User.findById(id))`, `return this.repo.find()` (TypeORM entities with `passwordHash`, `salt`, `refreshToken`, `apiKey`, `tenantId`), Mongoose documents without `select: false`/`toJSON` transform, Prisma `findMany()` with no `select` on models that have secrets, Sequelize `findAll()` without `attributes.exclude`.
- Unpaginated: `find()`/`findMany()`/`findAll()` with no `take`/`limit`; `limit` read from the query with no cap (`parseInt(req.query.limit)`); Mongoose `.find({})`.
- Validation: routes reading `req.body.x` directly with no schema; NestJS controllers without a global `ValidationPipe`; DTOs without decorators; `whitelist`/`forbidNonWhitelisted` off (mass assignment); `req.params.id` passed unparsed.
- Error shape: `res.status(400).json({ error: '...' })` in one file, `{ message }` in another, `{ success: false }` elsewhere; `err.stack` in responses; `res.send(err)` (serialises the whole error); no global error handler (Express default HTML error page); NestJS default `{ statusCode, message, error }` mixed with custom filters.
- Status codes: `res.json(created)` (200) on POST; `res.sendStatus(200)` on delete; `401` for forbidden; `500` for not found (`throw new Error`); `200` with `{ error }`.
- Naming/dates: snake_case from the DB leaking into JSON (`created_at` alongside `createdAt`); `Date` serialised via `toISOString()` (fine) vs `moment().format()` strings; numeric ids as strings in some routes; enums as numbers.
- Versioning: routers mounted at `/api` with no version; NestJS `enableVersioning` absent; `/v1` and unversioned routes both live.

## What "good" looks like
```ts
// main.ts (NestJS)
app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true, transform: true }));
app.useGlobalInterceptors(new ClassSerializerInterceptor(app.get(Reflector)));
app.enableVersioning({ type: VersioningType.URI, defaultVersion: '1' });
if (process.env.NODE_ENV !== 'production') SwaggerModule.setup('api-docs', app, SwaggerModule.createDocument(app, config));
// controller
@Controller('orders') @Version('1')
export class OrdersController {
  @Get() list(@Query() q: PageQueryDto) { const size = Math.min(q.pageSize ?? 20, 100); return this.svc.list(q.page ?? 1, size); }  // returns { items: OrderDto[], total, page, pageSize }
  @Post() @HttpCode(201) create(@Body() dto: CreateOrderDto) { ... }
}
export class CreateOrderDto { @IsArray() @ArrayMinSize(1) @ValidateNested({ each: true }) @Type(() => LineDto) lines: LineDto[]; @IsOptional() @MaxLength(32) couponCode?: string; }
export class User { @Exclude() passwordHash: string; }
// express: one problem-details error handler
app.use((err, req, res, next) => { const status = err.status ?? 500; res.status(status).type('application/problem+json').json({ type: 'about:blank', title: err.title ?? 'Error', status, detail: status < 500 ? err.message : undefined, instance: req.originalUrl }); });
```

## Manual trace checklist
1. `main.ts`/`app.ts`: Swagger mount and its env guard; global validation pipe/schema middleware; global error handler; versioning.
2. Endpoint table: list routes with no `limit`/`take` or an uncapped one; handlers returning ORM results with no projection.
3. Every route/DTO: schema or decorators present; unknown fields rejected; params typed.
4. Collect every `res.status(...).json({` shape and NestJS filter output; count distinct shapes.
5. Mongoose/TypeORM/Prisma models with secret fields: `select: false` / `@Exclude` / `omit` present.
6. Spec diff: previous `openapi.json` from git or the previous build vs current (`curl /api-docs-json` on dev) via `scripts/spec_diff.py`.

## Stack-specific false positives
- `res.json(entity)` for models with no sensitive fields and no relations (recommend DTO, Info).
- Swagger in production behind an authenticated gateway (confirm and record).
- Fastify's default error JSON (`{ statusCode, error, message }`) if it is the only shape and `err.stack` is not included.
- Mongoose `toJSON: { transform }` that deletes `password` globally.

## Tooling
`grep -rn "swaggerUi\|SwaggerModule\|@fastify/swagger" src`; `grep -rn "res\.status([0-9]*)\.json({" src | sed 's/.*json(//' | sort | uniq -c`; `grep -rn "findMany()\|find()\|findAll()" src`; `$AUDIT_CORE_ROOT/skills/audit-endpoint-inventory/scripts/inventory_endpoints.py`; `npx @redocly/cli lint openapi.yaml`; `oasdiff` or `scripts/spec_diff.py`.

## References
ASVS 13.1/13.2, OWASP API Security Top 10 2023, RFC 9457, NestJS validation/serialization/versioning docs, express-openapi-validator, Mongoose `select: false`.
