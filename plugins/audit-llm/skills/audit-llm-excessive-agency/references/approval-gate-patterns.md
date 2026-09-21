# Approval gate patterns by tool shape

| Tool shape | Weak pattern | Stronger pattern |
|---|---|---|
| Payment/refund | One tool takes amount and executes immediately | `propose_refund(order_id, amount)` returns a pending id capped server-side at the order total; `confirm_refund(pending_id, operator_token)` requires a human-issued token to actually execute |
| Data deletion | `delete_records(query)` runs immediately on whatever the model constructs | `stage_deletion(...)` returns a preview/count; a separate, human-triggered `execute_deletion(staged_id)` (outside the agent's own tool list) commits it |
| External communication (email/SMS/post) | `send_message(to, body)` sends immediately | Draft-and-approve: the agent can only create a draft; sending is a separate action outside the agent's tool access, or gated behind a rate-limited allowlist of recipients for low-risk cases |
| Admin/role changes | Agent has a generic `run_admin_command` tool | No single agent tool should be able to change roles/permissions at all; if the use case genuinely needs it, gate behind a dedicated, narrowly-scoped tool with its own explicit confirmation, never a general-purpose admin executor |

Credential scoping check: for each tool, ask "if this credential leaked or
was used by a compromised model, what's the blast radius?" A tool credential
that's scoped exactly to that tool's declared purpose limits it; a shared
service-role credential does not.
