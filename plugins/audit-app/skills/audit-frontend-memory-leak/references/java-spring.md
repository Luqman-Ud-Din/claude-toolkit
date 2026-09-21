# Java / Spring reference for audit-frontend-memory-leak

This skill audits frontend memory. A Spring backend in the same repo matters
only as the server end of long-lived client connections (STOMP over WebSocket,
raw WebSocket, SSE via `SseEmitter`/`Flux`). Check those pairings; defer the
rest to `audit-backend-resource-leak`.

## Stack markers

`pom.xml`/`build.gradle` with `spring-boot-starter-websocket` (STOMP, `@EnableWebSocketMessageBroker`),
`spring-boot-starter-webflux` (`Flux<ServerSentEvent>`), or `SseEmitter` in MVC controllers.
Frontend counterpart: `@stomp/stompjs`, `sockjs-client`, `EventSource`, `socket.io-client`.

## Where the relevant code lives

`config/WebSocketConfig.java`, `@MessageMapping` controllers, `@Controller` methods returning
`SseEmitter` or `Flux<ServerSentEvent<T>>`, `SimpMessagingTemplate` users, session registries
(`SimpUserRegistry`), `@EventListener(SessionDisconnectEvent.class)`; on the client,
`services/stomp.service.ts` or `lib/ws.ts`.

## Dangerous / interesting APIs and patterns (this skill's slice only)

- `SseEmitter` stored in a `List`/`Map` on subscribe with no removal in `onCompletion`,
  `onTimeout`, `onError`: each client-side leaked `EventSource` becomes a server-side leaked
  emitter (and a thread on the servlet stack).
- `SseEmitter(Long.MAX_VALUE)` (no timeout) combined with clients that never close.
- STOMP: per-session state in a `Map<String, ...>` keyed by `sessionId` without a
  `SessionDisconnectEvent` listener removing it.
- No `setMessageSizeLimit`/`setSendBufferSizeLimit` in `configureWebSocketTransport`: leaked
  subscribers buffer server messages until the broker throttles.
- WebFlux `Flux` SSE built from a hot `Sinks.Many` with `onBackpressureBuffer()` unbounded:
  leaked subscribers grow server buffers.
- Broadcasting full datasets (`convertAndSend("/topic/rows", allRows)`) - multiplies the
  client-side leak cost; note it in the client finding's Impact.

## What "good" looks like

```java
@GetMapping(path = "/api/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
public SseEmitter events() {
    SseEmitter emitter = new SseEmitter(30_000L);
    emitters.add(emitter);
    Runnable remove = () -> emitters.remove(emitter);
    emitter.onCompletion(remove); emitter.onTimeout(remove); emitter.onError(e -> remove.run());
    return emitter;
}
@EventListener
public void onDisconnect(SessionDisconnectEvent e) { sessionState.remove(e.getSessionId()); }
```
Client pairing: one STOMP client per session (`client.activate()` after login,
`client.deactivate()` on logout); components keep the `StompSubscription` returned by
`client.subscribe(...)` and call `.unsubscribe()` in their teardown.

## Manual trace checklist

1. Locate the WebSocket/SSE endpoints and the client module that connects. One connection per
   session or per component? The client side is the finding; server evidence goes in Impact.
2. Every server-side registry (emitters, sessions, subscriptions) has a removal path wired to
   completion/timeout/disconnect.
3. Timeouts configured (`SseEmitter` timeout, `spring.mvc.async.request-timeout`).
4. Client `subscribe` return values kept and unsubscribed.

## Stack-specific false positives

- `SimpMessagingTemplate` fan-out with no per-session state: no server-side leak.
- Reactive `Flux.interval(...)` per subscriber is cancelled when the client disconnects, as long
  as nothing caches the `Flux` with `.cache()`/`.replay()` unbounded.

## Tooling

Actuator `/actuator/metrics/executor.active` or a custom gauge of `emitters.size()` while the
frontend heap-snapshot procedure runs; `jcmd <pid> GC.class_histogram | grep SseEmitter`.

## Deferred to sibling skills

Connection pools, streams, executors, caches: `audit-backend-resource-leak`. STOMP destination
authorization: `audit-authz-and-access-control`.

## References

Spring WebSocket/STOMP: https://docs.spring.io/spring-framework/reference/web/websocket.html;
`SseEmitter`: https://docs.spring.io/spring-framework/reference/web/webmvc/mvc-ann-async.html;
CWE-401, CWE-772, CWE-400.
