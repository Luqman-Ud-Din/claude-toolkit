# Node / Express reference for audit-frontend-memory-leak

This skill audits frontend memory. A Node backend (Express, Fastify, NestJS)
in the same repo matters as the server end of `socket.io` / `ws` / SSE
connections, and - because it is the same language - as the place where
shared "isomorphic" modules (event buses, caches) may be imported by the
browser bundle too. Check those; defer the rest to `audit-backend-resource-leak`.

## Stack markers

`package.json` with `socket.io`, `ws`, `@nestjs/websockets`, `@nestjs/platform-socket.io`,
`sse-channel`, or hand-rolled `res.write` with `text/event-stream`. Frontend counterpart:
`socket.io-client`, `EventSource`, `WebSocket`.

## Where the relevant code lives

`src/socket.ts` / `gateway.ts` (Nest `@WebSocketGateway`), `server.ts` (`io.on('connection')`),
SSE routes, `src/shared/**` or a monorepo `packages/shared` imported by both server and client
(module-level `EventEmitter`, caches), `src/events.ts`.

## Dangerous / interesting APIs and patterns (this skill's slice only)

- `io.on('connection', socket => { registry.set(socket.id, ...) })` with no `socket.on('disconnect')`
  removal: each leaked client connection leaks a server entry.
- `socket.on(event, handler)` registered inside another handler (per message) - handlers stack
  per message on both ends; the client mirror is `socket.on` inside a component without `off`.
- SSE route storing `res` in an array without `req.on('close', ...)` removal; `while (true)`
  loops that do not check `res.writableEnded`.
- `EventEmitter` in a shared module with `setMaxListeners(0)` (warning silenced) - the
  "MaxListenersExceededWarning" is exactly the leak signal this skill wants; silencing it hides
  the client-side leak when the module is bundled for the browser.
- Server broadcasting full datasets on an interval (`io.emit('rows', all)`) - amplifies the
  client leak cost; note in Impact.
- Nest `@SubscribeMessage` gateways keeping `Map<clientId, Subscription>` without
  `handleDisconnect` cleanup.

## What "good" looks like

```ts
io.on('connection', socket => {
  const tenant = socket.data.tenant;
  socket.join(tenant);
  const onRows = (rows) => socket.emit('rows', rows);
  bus.on(`rows:${tenant}`, onRows);
  socket.on('disconnect', () => bus.off(`rows:${tenant}`, onRows));
});
// SSE
app.get('/api/events', (req, res) => {
  res.setHeader('Content-Type', 'text/event-stream');
  const send = (e) => res.write(`data: ${JSON.stringify(e)}\n\n`);
  bus.on('event', send);
  req.on('close', () => { bus.off('event', send); res.end(); });
});
```
Client pairing: a single `socket.io-client` instance in a session-scoped module; components call
`socket.on(name, handler)` in mount and `socket.off(name, handler)` in unmount; `EventSource`
instances are `close()`d in unmount.

## Manual trace checklist

1. Locate the socket/SSE server code and the client module that connects: one connection per
   session or per component? Client side is the finding; server evidence goes in Impact.
2. Every server-side registry keyed by socket/connection id has a `disconnect`/`close` removal.
3. Shared modules imported by the browser bundle: any `EventEmitter`, cache, or registry with
   `on`/`add` and no `off`/`delete`.
4. `setMaxListeners` calls: why was the warning raised?

## Stack-specific false positives

- `socket.on` inside `io.on('connection')` (once per connection) is correct; only nested
  registration per message is a smell.
- `res.on('close')` cleanup present but written as `req.on('aborted')`: still fine in Node 18+.

## Tooling

`node --inspect` + Chrome DevTools Memory on the server while the frontend heap-snapshot
procedure runs (search retainers for `Socket`, `ServerResponse`); `io.engine.clientsCount`
logged per minute; `process.on('warning')` to surface `MaxListenersExceededWarning`.

## Deferred to sibling skills

Pools, streams, timers, child processes, server caches: `audit-backend-resource-leak`.
Socket authentication: `audit-client-auth-and-storage`, `audit-authz-and-access-control`.

## References

socket.io server API (`disconnect` event): https://socket.io/docs/v4/server-api/;
Node `EventEmitter` listener limits: https://nodejs.org/api/events.html#emittersetmaxlistenersn;
CWE-401, CWE-772, CWE-400.
