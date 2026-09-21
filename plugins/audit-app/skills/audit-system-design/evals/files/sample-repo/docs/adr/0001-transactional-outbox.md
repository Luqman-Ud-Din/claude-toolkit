# ADR-0001: Publish integration events through a transactional outbox

Date: 2026-02-10

## Status

Accepted

## Context

Orders and invoices must be published to RabbitMQ reliably. Publishing directly
after SaveChanges can lose events when the broker is down.

## Decision

Every service writes integration events to an `OutboxMessages` table in the same
transaction as the business change. A background dispatcher publishes them and
marks them sent. No service calls `IBus.Publish` from a request handler.

## Consequences

Events are delayed by up to the dispatcher interval; at-least-once delivery, so
consumers must be idempotent.
