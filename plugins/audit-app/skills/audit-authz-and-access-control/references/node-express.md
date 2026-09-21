# Node / Express reference for audit-authz-and-access-control

## Stack markers
`package.json` with `express`/`fastify`/`koa`/`@nestjs/core`. Variants: Express router style vs NestJS decorators (`@Controller`, `@UseGuards`).

## Where the relevant code lives
`routes/`, `app.js`/`server.js`/`index.js` (middleware order), `controllers/`, `middleware/auth*.js`, `models/` (ownership queries). NestJS: `*.controller.ts`, `*.guard.ts`, `main.ts`.

## Dangerous / interesting APIs and patterns
- Missing auth: `router.get('/x', handler)` with no auth middleware before `handler`, in a router that is mounted without a global `app.use(requireAuth)`. Middleware order matters - a route defined before `app.use(auth)` is unprotected.
- IDOR: `Model.findById(req.params.id)` / `findByPk` / `findOne({ id })` without also constraining `userId`/`tenantId` to `req.user`.
- Mass assignment: `new Model(req.body)`, `Object.assign(model, req.body)`, `{ ...req.body }`, or Mongoose `Model.create(req.body)` where the schema includes `role`/`isAdmin`. Whitelist with `pick`/explicit fields.
- Privilege fields: `req.body.role`, `req.body.isAdmin`, `req.body.tenantId` read and trusted.
- Role enforcement: a `requireRole('admin')` middleware or NestJS `@Roles()` + `RolesGuard`. Checking `req.user.role` in the client is not enforcement.

## What "good" looks like
```js
router.get('/orders/:id', requireAuth, async (req, res) => {
  const order = await Order.findOne({ _id: req.params.id, userId: req.user.id });
  if (!order) return res.sendStatus(404);
  res.json(order);
});
// updates: pick allowed fields only
const { displayName, email } = req.body;         // never req.body.role
```

## Manual trace checklist
1. Read `app.js` middleware order - anything mounted before the auth middleware is public.
2. Every `findById`/`findByPk`/`findOne` in a route -> owner/tenant filter present?
3. Every create/update -> is the body whitelisted, or spread onto the model?
4. Background workers / queue consumers / webhooks -> do they set/verify user & tenant?

## Stack-specific false positives
Public routes (`/login`, `/health`) with no auth by design; `findById` in an admin route guarded by `requireRole('admin')`; `req.body` spread after an explicit `pick`/validation (Joi/zod) that strips unknown keys.

## Tooling
`npm audit`, `eslint-plugin-security`, `semgrep --config p/nodejs`. Live probe: `scripts/authz_probe.py`.

## References
CWE-306, CWE-862, CWE-863, CWE-639, CWE-915, CWE-602. ASVS 4.1/4.2. OWASP A01:2021.
