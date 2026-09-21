---
name: propose-llm-prompt-changes
description: Produces rewritten prompts as diffs against the originals, with reasoning for each change, to fix findings about clarity, contradictions, instruction/data separation, goal-based vs script-based framing, and intent-grounding behaviors (asking on ambiguity, honest limitation statements). Use it whenever the user asks to fix, rewrite, or improve a system prompt based on audit findings, wants a prompt diff with explained reasoning, or asks "how should we reword this prompt to fix X" - even when the user does not name this skill. Reads findings via shared-llm-finding-format and writes to audit/llm/proposals/propose-llm-prompt-changes.json per shared-llm-handoff-contract.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Propose: LLM prompt changes

Design principle in `llm-audit-skills.md` section 4: proposals reference
finding IDs, prefer code-level fixes over prompt changes, and state
trade-offs. This skill is specifically for the subset of findings where a
prompt rewrite genuinely is the right primary fix (clarity, framing, honest
scoping) - not a substitute for a code-level control when one is needed.

Prerequisites: `shared-llm-finding-format`, `shared-llm-owasp-mapping`,
`shared-llm-handoff-contract`.

## When a prompt change is (and isn't) the right fix

- **Right**: `Prompt & Context Engineering` findings (contradictions,
  vagueness, script-vs-goal framing), `Intent Grounding & Adaptability`
  findings about ambiguity handling or honest limitation statements, and
  the wording half of a `Jailbreak Resistance` finding where the system
  prompt itself invites bypass (e.g. it explicitly grants an "act as X"
  override).
- **Wrong as the *primary* fix, right as defense in depth**: `Excessive
  Agency`, `Guardrails`, and `Prompt Injection` findings where the real fix
  is a code-level control (an approval gate, a code-enforced check, a
  structural instruction/data boundary) - propose the prompt wording
  improvement only alongside a note that `propose-llm-controls` owns the
  actual fix, and never present a prompt-only patch as resolving one of
  these findings on its own.

## Workflow

1. **Read the finding(s)** by id, and the current prompt text via
   `explore-llm-prompts.json` or a direct read of the file it names.
2. **Draft the rewrite** addressing the specific defect named in the
   finding - don't rewrite the whole prompt wholesale when the finding is
   about one contradictory line; a large diff makes the actual fix harder to
   review and easier to introduce a new regression into.
3. **Produce a diff-style output**: original text struck/marked, new text
   shown, with a short reasoning note per changed section tying it back to
   the finding id.
4. **State trade-offs.** A more cautious "always ask before acting" framing
   can add friction/latency to legitimate simple requests; a more explicit
   honesty instruction can increase refusal rate on edge cases. Say so rather
   than presenting the change as free.
5. **Recommend a verification path.** Point at `propose-llm-eval-suite` to
   generate a test that fails on the old prompt and passes on the new one -
   a prompt fix with no way to confirm it worked is a common way regressions
   slip back in on the next edit.
6. **Write the proposal** to
   `audit/llm/proposals/propose-llm-prompt-changes.json` per
   `shared-llm-handoff-contract`'s schema, with `finding_refs` set.

## Bundled files

- `references/diff-format.md` - the exact before/after/reasoning block format to use for a prompt diff.
