# Handoff contract - filled examples

## `audit/llm/explore/explore-llm-tools-and-permissions.json`

```json
{
  "skill": "explore-llm-tools-and-permissions",
  "generated_at": "2026-09-20T10:00:00Z",
  "root": "/repo",
  "summary": "The support agent can call 4 tools; refund_order is the only irreversible one and has no approval gate.",
  "items": [
    {
      "id": "tool-refund_order",
      "location": "src/agent/tools/refund_order.py:1",
      "detail": {
        "schema": {"order_id": "string", "amount": "number"},
        "touches": "payments DB, Stripe refund API",
        "credentials": "service-role Stripe key (full account scope)",
        "reversible": false,
        "approval_required": false
      }
    }
  ],
  "open_questions": ["is refund_order reachable from a customer-facing chat, or only an internal admin agent?"]
}
```

## `audit/findings/audit-llm-excessive-agency.json` (unchanged audit-finding-writer contract, LLM prefix/Area)

```json
{
  "findings": [
    {
      "id": "LLM-EA-003",
      "title": "refund_order tool has no approval gate before an irreversible Stripe refund",
      "severity": "High",
      "confidence": "confirmed",
      "location": "src/agent/tools/refund_order.py:1",
      "evidence": "tool schema accepts amount unconstrained; called directly from agent loop, no human-in-the-loop step",
      "impact": "A successful prompt injection or a model reasoning error can trigger a real refund with no human check.",
      "remediation": "Require a human-approved confirmation step before refund_order executes, and cap amount server-side to the order's paid total.",
      "references": ["OWASP LLM06 / ASI02", "Related: LLM-PI-001"]
    }
  ]
}
```

## `audit/llm/proposals/propose-llm-controls.json`

```json
{
  "skill": "propose-llm-controls",
  "generated_at": "2026-09-21T09:00:00Z",
  "proposals": [
    {
      "id": "approval-gate-refund",
      "finding_refs": ["LLM-EA-003"],
      "title": "Add a human approval gate before refund_order executes",
      "change": "Split refund_order into propose_refund (returns a pending refund id) and confirm_refund (requires a signed operator confirmation token); the agent can only call propose_refund.",
      "trade_offs": "Adds one round trip and an operator queue for refunds; acceptable for an irreversible financial action.",
      "effort": "M"
    }
  ]
}
```
