# Code-enforced vs. prompt-only - worked examples

| Rule | Code-enforced version | Prompt-only version (flag if safety/business-critical) |
|---|---|---|
| "Never refund more than the order total" | Server validates `amount <= order.total` before calling the payment API, independent of what the model requests | The system prompt says "never refund more than the order total"; the tool accepts any `amount` and executes it |
| "Don't include PII in logs/output" | A redaction pass runs on every model response before it's logged or returned | The prompt says "don't include personal information"; nothing checks the actual output |
| "Only answer questions about our product" | A classifier or retrieval-grounding check runs before/after generation to catch off-topic answers | The prompt says "only discuss our product"; no check on the response |
| "Output must be valid JSON matching this schema" | Structured output / function-calling mode with schema validation and a retry-on-failure loop | The prompt describes the desired JSON format; the app trusts and parses whatever comes back, possibly crashing or misbehaving on malformed output |

A hybrid is common and fine: prompt guidance plus a code-enforced backstop.
The finding is specifically for critical rules that have *no* backstop at
all - name the exact rule and exact tool/output path affected, not "the
guardrails are weak" in general.
