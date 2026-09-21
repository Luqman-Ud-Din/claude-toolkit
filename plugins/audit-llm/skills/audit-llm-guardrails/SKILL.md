---
name: audit-llm-guardrails
description: Reviews an LLM application's input and output guardrail layers, checking whether safety and business rules are actually enforced in code (a classifier, a deterministic check, a second model call) versus existing only as wording inside the system prompt, and confirms model output is treated as untrusted before it is rendered, executed, or passed downstream. Use it whenever the user asks about guardrails, content filters, output validation, moderation layers, whether a rule is "just in the prompt" or actually enforced, or whether AI-generated output is safely handled before display or further processing - even when the user does not name this skill. Writes findings with Area "Guardrails" (prefix GR) to audit/findings/audit-llm-guardrails.json.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Audit: LLM guardrails

OWASP LLM05. Can run standalone; uses stack/explore output when present.

Prerequisites: `shared-llm-context-bootstrap`, `shared-llm-probe-runner`,
`shared-llm-finding-format`, `audit-finding-writer`.

## Workflow

1. **Bootstrap.** `shared-llm-stack-detection`'s `guardrails` category names
   any guardrail library present; verify each is actually invoked on the
   request path, not just imported (see that skill's sanity-check step).
   Absent an explore map, grep for guardrail library calls, output-parsing/
   validation code, and moderation-endpoint calls directly.
2. **Classify every rule the app is supposed to enforce** (from prompts,
   docs, or the user's description of intended behavior) as one of:
   - **Code-enforced** - a deterministic check, schema validation, allow/deny
     list, or classifier call that runs regardless of what the model outputs,
     and that the model cannot talk its way around.
   - **Prompt-only** - the rule exists solely as an instruction to the model;
     nothing in code verifies the model actually followed it.
   A rule that's prompt-only is not automatically a finding by itself (some
   rules are genuinely low-stakes), but every prompt-only rule that's also
   safety- or business-critical (payment amounts, PII handling, content that
   could cause real harm) is.
3. **Check output handling downstream.** Is model output rendered as raw
   HTML/Markdown without sanitization (an XSS vector if the output can
   contain attacker-influenced content - overlaps `audit-frontend-xss-and-dom-safety`,
   cross-reference rather than duplicate), passed to a shell/eval/SQL builder
   (overlaps `audit-injection-vulnerabilities`), or fed directly into another
   tool call with no validation of the tool's actual argument constraints?
   "Improper output handling" (LLM05) is specifically about trusting model
   output the way you'd trust validated user input - it deserves the same
   scrutiny.
4. **Probe for bypasses** of code-enforced guardrails using
   `shared-llm-payload-library`'s `paraphrase_variants` and `jailbreak_encoding`
   categories through `shared-llm-probe-runner` - a keyword-based filter is
   the most common guardrail that a rephrased or encoded request slips past.
5. **Rate and write findings** via `audit-finding-writer`, Area "Guardrails" /
   prefix `GR`.

## Bundled files

- `references/enforcement-classification.md` - worked examples of code-enforced vs. prompt-only for common rule types (PII redaction, refund limits, content policy, output format).
