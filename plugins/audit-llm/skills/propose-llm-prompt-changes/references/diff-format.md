# Prompt diff format

```markdown
### Fix for LLM-IG-002: agent doesn't ask before an ambiguous restock action

**Before** (`src/prompts/inventory_agent.py:18`):
> When stock is low, restock the item.

**After:**
> When stock is low, ask the user whether to create a purchase order or just
> flag the item for manual review, unless they've already told you which
> they prefer for this kind of request.

**Reasoning:** The original instruction gives the agent no branch for
ambiguity, so it silently picked the purchase-order path (which spends
money) every time. The rewrite makes the ambiguity explicit and gives the
agent an escape hatch for when the user has already stated a preference, so
it doesn't ask redundantly on every single low-stock item in a batch.

**Trade-off:** Adds one clarifying round-trip the first time this comes up
in a session; acceptable given the action spends real money.

**Verify with:** propose-llm-eval-suite - a test case sending an ambiguous
restock request and asserting the response either asks or states an
explicit assumption, not silently the purchase-order action.
```
