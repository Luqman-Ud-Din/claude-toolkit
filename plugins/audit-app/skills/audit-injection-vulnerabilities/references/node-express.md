# Node / Express (NestJS, Fastify, Koa) reference for audit-injection-vulnerabilities

## Stack markers
`package.json` with `express`, `@nestjs/core`, `fastify`, `koa`, `hapi`. Data layers: `pg`, `mysql2`, `mssql`, `sequelize`, `typeorm`, `prisma`, `knex`, `mongoose`, `mongodb`.

## Where the relevant code lives
`routes/**`, `controllers/**`, `*.controller.ts`, `*.service.ts`, `repositories/**`, `db/**`, `prisma/**` (`$queryRaw`), `jobs/**`/`workers/**` (BullMQ payloads), `utils/exec*.ts`, upload handlers (`multer`), proxy/fetch helpers. Sources: `req.params`, `req.query`, `req.body`, `req.headers`, `req.file.originalname`, Nest `@Param()`/`@Query()`/`@Body()`, Fastify `request.query`. Remember `req.query.x` may be an **array or object** (`?x[$gt]=`) - qs parsing feeds NoSQL injection.

## Dangerous / interesting APIs and patterns
- SQL: `` client.query(`... ${x}`) ``, `pool.query("..." + x)`, `sequelize.query(` with template literal, `knex.raw(`/`whereRaw(`/`orderByRaw(` with `${}`, TypeORM `.query(`, `createQueryBuilder().where("col = '" + x`, `orderBy(userString)`, Prisma `$queryRawUnsafe(` / `$executeRawUnsafe(` (the tagged `$queryRaw` template is parameterized), `mssql` `request.query(str)` without `.input(`.
- NoSQL: `Model.find(req.body)`, `find({ username: req.body.username })` where value may be an object (`{$gt: ""}`), `$where:`, `mapReduce` with user JS, `db.collection.find(JSON.parse(user))`, `Model.findOne({ [req.query.field]: ... })`.
- CMD: `child_process.exec(`, `execSync(`, `spawn(cmd, { shell: true })`, `spawn("sh", ["-c", ...])`, `execFile("bash"`, `shelljs.exec(`, template literals inside any of these.
- PATH: `path.join(root, req.params.name)` (`..` walks out; `path.join` normalizes but does not confine), `path.resolve(user)`, `fs.readFile|readFileSync|createReadStream|writeFile|unlink|stat(`, `res.sendFile(`, `res.download(`, `express.static` with a dynamic root, `require(userString)`, `import(user)`, `multer` `filename` callback using `file.originalname`.
- LDAP: `ldapjs` `client.search(base, { filter: "(uid=" + x })`, `ldap-authentication` with unsanitized `userSearchBase`.
- XPATH: `xpath.select("//user[@name='" + x`, `libxmljs` `.find(`; also `libxmljs.parseXml(x, { noent: true })` (XXE).
- TMPL: `ejs.render(userString`, `pug.compile(user`, `Handlebars.compile(user`, `nunjucks.renderString(user`, `_.template(user`, `new Function(`, `vm.runInNewContext(user` (sandbox escapes), `eval(`.
- SSRF: `fetch(req.body.url)`, `axios.get(user)`, `http.get(user)`, `got(user)`, `request(user)`, `node-fetch`, `undici.request(user)`, `new URL(input)` handed to a client without a host check, image proxies, `puppeteer.goto(user)`, webhook testers, `open-graph` scrapers.
- DESER: `node-serialize` `unserialize(`, `serialize-javascript` used in reverse, `js-yaml` `load(` with `DEFAULT_FULL_SCHEMA` / `yaml.load` pre-4 without `safeLoad`, `JSON.parse` + deep merge into objects (prototype pollution `__proto__`, CWE-1321), `lodash.merge(target, req.body)`, `qs` with `allowPrototypes: true`, `xml2js` `explicitRoot` misuse (not deser, skip), `v8.deserialize(` on untrusted bytes.

## What "good" looks like
```ts
// SQL - placeholders; sort allow-listed
const rows = await pool.query('SELECT * FROM sales WHERE branch_id = $1', [branchId]);
const sort = SORT_COLUMNS[req.query.sort as string] ?? 'created_on';
await prisma.$queryRaw`SELECT * FROM sales WHERE branch_id = ${branchId}`;   // tagged template = params

// NoSQL - coerce types, reject operators
const username = String(req.body.username);          // never pass an object
app.use(mongoSanitize());                            // express-mongo-sanitize strips $ and .

// PATH - basename + confine
const name = path.basename(req.params.name);
const full = path.resolve(ROOT, name);
if (!full.startsWith(ROOT + path.sep)) return res.sendStatus(404);

// CMD - execFile with array args, no shell
await execFile('convert', [full, out]);

// SSRF - parse and allow-list
const u = new URL(input); if (u.protocol !== 'https:' || !ALLOWED_HOSTS.has(u.hostname)) throw new BadRequestException();

// DESER - JSON only; js-yaml >= 4 load() is safe by default; validate with zod before merging.
```

## Manual trace checklist
1. List/search endpoints: `sort`, `order`, `filter`, `columns` query params into `orderByRaw`, `knex.raw`, or Mongo field names.
2. Login/lookup handlers: can `req.body.password` or `username` be an object? (Nest `ValidationPipe` with `whitelist` + DTO types prevents this; plain Express does not.)
3. Upload/download: `multer` storage `filename`, `res.download(path.join(...))`, "export by filename" routes.
4. Any `fetch`/`axios` whose URL or `baseURL` comes from the request or from a user-editable DB row (webhook URLs, store domains).
5. Job processors (`bull`, `agenda`): payload shapes and who can enqueue.
6. Object merge utilities receiving `req.body` (prototype pollution) - report as DESER class with CWE-1321.

## Stack-specific false positives
- `` prisma.$queryRaw`...${x}` `` (tagged) and `Prisma.sql` are parameterized; `$queryRawUnsafe` is not.
- `knex.raw('now()')` with no interpolation; `whereRaw('?? = ?', [col, val])` binds both.
- `exec('git rev-parse HEAD')` fully literal.
- `path.join(__dirname, 'templates', 'x.html')` constants.
- `eval`/`new Function` inside test files or a bundler shim.
- `axios.create({ baseURL: config.apiUrl })` + `/items/${id}` where `id` is validated numeric.

## Tooling
- `npx eslint --plugin security --rule 'security/detect-child-process: error' ...` (eslint-plugin-security: detect-child-process, detect-non-literal-fs-filename, detect-eval-with-expression, detect-non-literal-regexp).
- `semgrep --config p/nodejs --config p/expressjs` (`javascript.express.security.injection.*`, `ssrf`, `path-traversal`).
- `npx njsscan <dir>`.

## References
OWASP NodeJS Security cheat sheet; Prisma raw query docs; Mongoose "query injection" notes; express-mongo-sanitize; Node `child_process` docs (shell option). CWE-89, 943, 78, 22, 918, 502, 1321, 95; ASVS 5.3.x, 5.5.x, 12.3.x, 12.6.1; OWASP A03/A08/A10:2021.
