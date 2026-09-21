# Design-pattern catalog

Only these patterns may be named in a `Pattern` field. Each entry: the problem
it solves, when to apply it, when it is overkill, and a brief example in the
context of a business application preparing for international rollout.

Contents: Strategy - Specification - State machine - Domain events /
event-driven - Saga / process manager - Repository - Anti-corruption layer -
Adapter / Ports-and-adapters - Factory - Policy object - Feature toggles -
Multi-tenancy context - Outbox - CQRS

---

## Strategy

**Problem it solves.** A calculation or decision varies by some dimension
(country, currency, plan, carrier) and is currently implemented as a chain of
conditionals that every new variant extends.

**When to apply.** The BLD names a rule that differs by market or tenant (tax
calculation, rounding, invoice numbering, shipping cost) and the architecture
shows `if`/`switch` on country or currency in more than one place, or in a
place that will be edited for every new market.

**When it is overkill.** One variant exists today and the second is speculative;
or the variation is a single value (a rate) that belongs in a configuration
table, not in code.

**Example.** `TaxCalculator` interface with `NlVatCalculator`,
`SaVatCalculator`, `PkSalesTaxCalculator`; resolved by the customer's tax
jurisdiction. The controller no longer knows any rate.

---

## Specification

**Problem it solves.** Business predicates ("order is confirmable", "customer is
within credit limit", "product is sellable in this market") are duplicated in
queries, guards and reports, and drift apart.

**When to apply.** The BLD has a rule enforced in two or more places with
different logic, or the same predicate appears as both an in-memory check and a
database `where` clause.

**When it is overkill.** The predicate is used once and is three lines long.
Do not build a generic composable specification framework for two rules.

**Example.** `OpenExposureSpecification` defines "open" (status in
confirmed/shipped/delivered and unpaid) once, used both by the credit check and
by the reminder job's query.

---

## State machine

**Problem it solves.** Entity status transitions are scattered: some guarded,
some set directly by controllers or jobs, with no single definition of allowed
moves and their side effects.

**When to apply.** The BLD lists lifecycle states for an entity and the
architecture shows more than one component writing the status column, or the
transition table exists but is bypassed.

**When it is overkill.** The entity has two states and one transition; a
boolean and a timestamp are enough.

**Example.** `OrderStateMachine.transition(order, 'shipped', context)` is the
only code path that changes `orders.status`; the shipping controller calls it
instead of patching the row.

---

## Domain events / event-driven

**Problem it solves.** A workflow's side effects (send e-mail, adjust stock,
submit to tax authority, sync to marketplace) are called inline from the rule
that triggers them, coupling the rule to every downstream concern and making
the request slow and fragile.

**When to apply.** The BLD workflow has terminal outcomes that fan out to
integrations or other modules, and the architecture shows those calls inside the
service method or controller; or the BLD implies eventual behaviour ("customer
is notified", "ledger is updated") that need not complete in the request.

**When it is overkill.** The side effect must be transactional with the change
(then it is not a side effect), or there is exactly one consumer and it is in
the same module - a direct call is clearer. Do not introduce a message broker
for in-process events.

**Example.** `OrderConfirmed` event raised by the domain; handlers reserve stock
and queue the confirmation e-mail. In-process dispatcher first; a broker only
when handlers live in another deployable unit.

---

## Saga / process manager

**Problem it solves.** A single business workflow spans several services or
components with no owner: each step calls the next, no one can resume or
compensate after a failure midway, and the BLD's "terminal outcomes" are not
guaranteed.

**When to apply.** The BLD workflow crosses two or more deployable units or
external systems with side effects (payment captured, then stock reserved, then
tax authority notified), and the architecture shows a synchronous chain with no
compensation.

**When it is overkill.** All steps are in one process and one database
transaction covers them; or failure handling is "return an error and let the
user retry" and the BLD accepts that. A saga adds state, timeouts and
compensating actions - only pay for it when partial completion is a real
business problem.

**Example.** `OrderFulfilmentProcess` records each step (paid, reserved,
shipped, invoiced) and knows how to compensate (refund, release stock) when a
later step fails.

---

## Repository

**Problem it solves.** Data access is scattered through controllers, jobs and
services as raw ORM queries, so tenant filters, soft-delete conventions and
"open order" definitions are repeated and sometimes forgotten.

**When to apply.** The architecture shows ORM calls in the controller or job
layer, or the BLD notes a query convention (soft delete, tenant/branch filter)
that is applied inconsistently.

**When it is overkill.** The ORM already provides the abstraction (global
query filters, scoped model classes) and all access goes through one layer; a
repository per table that only wraps `findById` adds nothing.

**Example.** `OrderRepository.openForCustomer(customerId)` applies the tenant
and soft-delete filters and the "open" definition; jobs and controllers use it
instead of `Order.query().where(...)`.

---

## Anti-corruption layer

**Problem it solves.** An external system's model (tax authority payload,
marketplace product, payment provider's intent object) leaks into the domain,
so domain code changes when the external API changes and cannot be tested
without it.

**When to apply.** The architecture shows provider SDK types or payload shapes
used in services or entities, or the BLD's integrations section notes
assumptions baked in by the provider (currency, identifiers, status codes).

**When it is overkill.** The integration is a one-line notification with no
model of its own, or the external model is already the domain's (a shared
internal library).

**Example.** `FbrInvoiceTranslator` maps the domain `Invoice` to the FBR
submission payload and maps FBR responses to domain `SubmissionResult`; the
service never sees FBR field names.

---

## Adapter / Ports-and-adapters

**Problem it solves.** The domain depends on a concrete provider (one payment
gateway, one SMS vendor, one carrier), so adding a regional alternative means
changing business code.

**When to apply.** The BLD or target markets require a second provider for the
same business function, and the architecture shows the domain calling a
concrete SDK or module directly.

**When it is overkill.** There is and will be one provider, and the call site
is a single function that can be swapped later; an interface with one
implementation is fine only when the second is planned.

**Example.** `PaymentPort.charge(money, reference)` implemented by
`StripeAdapter` and `JazzCashAdapter`; the adapter chosen by the tenant's market
configuration.

---

## Factory

**Problem it solves.** Choosing which strategy, adapter or configuration
applies (for a country, tenant or plan) is repeated at every call site.

**When to apply.** Once Strategy or Adapter exists and the architecture shows
the selection logic (`if country == ...`) reappearing at call sites.

**When it is overkill.** One call site, or a dependency-injection container
already does the selection.

**Example.** `TaxCalculatorFactory.forJurisdiction(code)` returns the right
`TaxCalculator`; it reads the market configuration table, not a switch.

---

## Policy object

**Problem it solves.** A business decision with several inputs (can this user
cancel this order? which invoice template applies? what is the credit-check
threshold?) is embedded in a controller or scattered across guards, and varies
by tenant or plan.

**When to apply.** The BLD has an authorization-like or configuration-like rule
("only branch managers may...", "tenants on the Pro plan may...") that the
architecture implements inline, or that changes per market.

**When it is overkill.** The rule is a single role check that the framework's
authorization attribute already expresses.

**Example.** `CancellationPolicy.canCancel(order, actor, tenantSettings)` is
the one place that knows cancellation rules; the controller asks it and returns
403 or proceeds.

---

## Feature toggles

**Problem it solves.** Capabilities must be enabled per market, tenant or plan
(e-invoicing for one country, a payment method for another) and are currently
either always on, or gated by code branches tied to deployments.

**When to apply.** The BLD's rules or the target markets imply features that
apply in some markets and not others, and the architecture has no toggle
mechanism or one without a tenant/market dimension.

**When it is overkill.** A toggle for something that will never be turned off,
or so many toggles that combinations cannot be tested - keep toggles few,
named, and remove them when the rollout completes.

**Example.** `features.isEnabled('e-invoicing', tenant)` reads a per-tenant
configuration; the invoicing workflow consults it once at the submission step.

---

## Multi-tenancy context

**Problem it solves.** The current tenant, locale, currency, time zone or region
is held in a static/global or re-derived ad hoc, so jobs, background threads and
nested calls can act on the wrong tenant or the wrong locale.

**When to apply.** The architecture's cross-cutting table shows tenant or locale
selected by a static holder, a thread-local without scoping, or nothing at all;
or the BLD's rules depend on tenant/market values that some entry points (jobs,
webhooks) do not set.

**When it is overkill.** A single-tenant, single-market deployment with no plan
to change - then a configuration object is enough.

**Example.** `RequestContext { tenantId, branchId, locale, currency, timeZone,
region }` created by middleware from the token and tenant settings, passed or
scoped (async-local / DI scope) through every call, and constructed explicitly
by jobs per tenant they process.

---

## Outbox

**Problem it solves.** A database change and a message or external call must
both happen or neither (order confirmed and e-invoice submitted; payment
recorded and receipt e-mailed), but today the call is made after the commit
and lost on failure, or before it and sent for a rolled-back change.

**When to apply.** The BLD workflow has an integration side effect that must
not be lost (fiscal submission, notification with legal weight, marketplace
sync), and the architecture shows it called directly from the service.

**When it is overkill.** The side effect is best-effort and re-derivable (a
cache warm, an analytics ping), or there is no concurrency and a retry on the
next request is acceptable.

**Example.** `outbox_messages` table written in the same transaction as the
order; a worker publishes rows and marks them sent; the e-invoice submission is
the consumer.

---

## CQRS

**Problem it solves.** Read models (dashboards, reports, lists with heavy
joins) and write models (rules, invariants) pull the same entities in
incompatible directions, and one side degrades the other.

**When to apply.** Only when the architecture shows a measured problem: reporting
queries that block transactional writes, or a domain model contorted to serve
list screens. Rarely justified by the BLD alone.

**When it is overkill - strong warning.** Almost always, for a business
application of this kind. Separate read and write models double the surface
area, introduce eventual consistency into screens users expect to be immediate,
and require a synchronisation mechanism (events, projections) that must itself
be operated. Do not recommend CQRS to fix rule placement, variation points or
integration seams; those are solved by the patterns above. Recommend it only
with a named, measured read/write conflict and after the other steps of the
roadmap are done - and even then, prefer a read-only replica or materialised
views first.

**Example.** A `sales_summary_daily` projection updated from `OrderPaid` events,
used by the dashboard; the order aggregate is untouched. Note the projection lag
in the UI.
