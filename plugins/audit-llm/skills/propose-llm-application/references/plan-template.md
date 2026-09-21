# Merged remediation plan structure

```markdown
# LLM Application Remediation Plan

## Must fix before shipping
Ordered by severity, then effort-vs-impact. Each item:
- **[LLM-EA-003]** refund_order has no approval gate - see propose-llm-controls proposal `approval-gate-refund` (Effort: M)

## Fast-follow (post-launch acceptable)
Same format, lower urgency items.

## Verification
Which proposed fixes have a corresponding propose-llm-eval-suite case already drafted, and which still need one.

## Open items
Findings that couldn't be routed cleanly (missing info, needs a product decision, spans an Area with no clear owning propose skill) - named explicitly rather than silently dropped.
```
