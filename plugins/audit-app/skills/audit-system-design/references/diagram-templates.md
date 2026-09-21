# Diagram templates (Mermaid)

All diagrams in the report are Mermaid text so they render in Markdown and
diff in git. Keep node ids short and stable; put the human name in the label.
Mark single-instance infrastructure with `x1` in the label and style it.

## Conventions
- `[Name]` service/module, `[(Name)]` database, `{{Name}}` queue/broker, `[/Name/]` external system, `((Name))` client.
- Solid arrow `-->` synchronous call; dotted `-.->` asynchronous (publish/consume, webhook); thick `==>` bulk/batch.
- Edge label: protocol and auth (`HTTPS+JWT`, `AMQP`, `TDS`).
- One `subgraph` per deployment/trust zone.
- `classDef spof fill:#fdd,stroke:#c00;` and `class Q spof;` for single points of failure.

## Component / data-flow
```mermaid
flowchart LR
  classDef spof fill:#fdd,stroke:#c00,stroke-width:2px;
  SPA((Angular SPA)) -->|HTTPS+JWT| GW[Ocelot gateway]
  GW --> ACC[Account.MicroAPI]
  GW --> PRD[Product.MicroAPI]
  ACC --> MDB[(Master DB)]
  PRD --> TDB[(Tenant DB per company)]
  PRD -.->|AMQP publish| Q{{RabbitMQ x1}}
  Q -.->|consume| NTF[InvSMS worker]
  PRD -->|HTTPS| FBR[/FBR tax API/]
  NTF -->|HTTPS| SMS[/SMS provider/]
  class Q spof
```

## Trust boundaries
```mermaid
flowchart TB
  subgraph internet[Internet - untrusted]
    U((Browser / mobile))
  end
  subgraph edge[Edge - TLS terminates, JWT validated]
    GW[Gateway]
  end
  subgraph internal[Internal network - trusts forwarded identity]
    S1[Service A]
    S2[Service B]
    J[Job host]
  end
  subgraph data[Data zone]
    DB[(DB)]
    Q{{Broker}}
  end
  subgraph third[Third parties]
    X[/Tax API/]
  end
  U -->|HTTPS + JWT| GW
  GW -->|HTTP, JWT forwarded, re-validated?| S1
  GW -->|HTTP| S2
  S1 -->|TDS, secret from env| DB
  S1 -.->|AMQP, plaintext?| Q
  J -->|no auth - internal only?| S2
  S2 -->|HTTPS, API key in config| X
```
Under the diagram, one bullet per boundary crossing: what is checked, what is
trusted without checking, how the secret for that edge is supplied.

## Sequence for the critical flow
```mermaid
sequenceDiagram
  participant C as Client
  participant G as Gateway
  participant P as Product API
  participant D as Tenant DB
  participant Q as Broker
  participant W as Worker
  C->>G: POST /productapi/sale (JWT)
  G->>P: forward
  P->>D: INSERT Sale, SaleDetails (tx)
  P-->>Q: publish SaleCreated (after commit? inside tx?)
  P-->>C: 200
  Q-->>W: SaleCreated
  W->>D: UPDATE Stock (idempotent?)
```
Annotate the questions in parentheses; each unanswered one is a trace item.

## Module dependency graph
`scripts/module_graph.py --mermaid` emits this shape; cycles are drawn in red.
```mermaid
flowchart LR
  Orders.Api --> Billing.Core
  Billing.Core --> Orders.Api
  Orders.Api --> Shared.Contracts
  Billing.Core --> Shared.Contracts
  linkStyle 0,1 stroke:#c00,stroke-width:2px;
```

## Trust-boundary table (companion to the diagram)
| Edge | From zone | To zone | Transport | Identity carried | Verified at target? | Secret source |
|---|---|---|---|---|---|---|
| SPA -> Gateway | internet | edge | HTTPS | JWT | yes | n/a |
| Gateway -> Product API | edge | internal | HTTP | JWT forwarded | yes (`[Authorize]`) | n/a |
| Product API -> Tenant DB | internal | data | TDS | SQL login | yes | appsettings (finding if literal) |
