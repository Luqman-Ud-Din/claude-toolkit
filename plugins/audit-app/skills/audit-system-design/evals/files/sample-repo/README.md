# Ledger platform

Backend for the ledger product. Two services behind the gateway plus a worker.

## Architecture

```mermaid
flowchart LR
  SPA[Angular SPA] --> GW[Gateway]
  GW --> Orders.Api
  GW --> Payments.Service
  Orders.Api --> OrdersDb[(orders-db)]
  Payments.Service --> PaymentsDb[(payments-db)]
  Orders.Api --> Redis[(Redis cache)]
  Orders.Api -.-> RabbitMQ{{RabbitMQ cluster}}
  RabbitMQ -.-> Notifications.Worker
```

- `Orders.Api` owns orders and invoices.
- `Payments.Service` owns payments and talks to the card provider.
- Events are published through the outbox (see ADR-0001).
- `Redis cache` fronts the product catalogue.
