---
name: explore-llm-prompts
description: Inventories every system prompt, prompt template, and instruction fragment in an LLM application - where it lives, what it's for, how it's assembled at runtime, which variables get injected into it, and whether it's version-controlled alongside the code - and writes audit/llm/explore/explore-llm-prompts.json. Use it whenever the user asks to find, list, or review system prompts, prompt templates, or "what instructions is the AI actually given", wants a prompt inventory before editing one, or asks where prompts are stored and how they get built - even when the user does not name this skill. Feeds audit-llm-prompt-and-context-engineering, audit-llm-prompt-injection, and propose-llm-prompt-changes.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Explore: LLM prompts

A map of every instruction fragment that reaches the model, not a review of
whether the wording is good - that judgment belongs to
`audit-llm-prompt-and-context-engineering` and `propose-llm-prompt-changes`.

Prerequisites: `shared-llm-stack-detection`, `shared-llm-context-bootstrap`,
`shared-llm-trust-classification`, `shared-llm-handoff-contract`.

## Workflow

1. **Bootstrap and locate.** Use the stack detection evidence to find prompt
   construction sites: string literals near `system=`, `SystemMessage(`,
   `role: "system"`, prompt template files (`.txt`, `.md`, `.jinja`, `.hbs`,
   framework-specific template classes), and any prompt stored outside the
   repo (a database row, a CMS field, a vendor prompt-management product) -
   note those as "not version-controlled" explicitly, since that's a real
   operational gap `audit-llm-prompt-and-context-engineering` will flag.
2. **For each prompt, record:**
   - **Purpose** - what behavior it's steering (one sentence).
   - **Runtime assembly** - static string, or built by concatenating a
     template with variables? List every variable substituted in and its
     source (a config value, a retrieved doc, user profile data, another
     model's output).
   - **Trust of injected variables** - classify each substituted variable with
     `shared-llm-trust-classification`. A prompt that splices an untrusted
     variable directly into the instruction-bearing text (not clearly
     delimited as data) is exactly what `audit-llm-prompt-injection` needs
     flagged precisely.
   - **Version control** - is this prompt's text a file in the repo, or does
     it live somewhere that changes without a code review / git history?
3. **Note prompt sprawl.** If the same instruction (a tone guideline, a safety
   rule) is duplicated across multiple prompts with drift between copies,
   record it - that's a maintainability and consistency risk worth a
   `Prompt & Context Engineering` finding even without any security angle.
4. **Write the map** with `items[].detail` shaped as:

   ```json
   {
     "purpose": "primary support-agent system prompt",
     "kind": "static-with-template",
     "variables": [{"name": "user_bio", "source": "users.bio column", "trust_tier": "semi-trusted", "delimited": false}],
     "version_controlled": true,
     "file": "src/prompts/support_agent.py:12"
   }
   ```

5. **Say what you couldn't find.** A model called with no explicit system
   prompt (provider default only) is worth noting, not skipping.

## Bundled files

- `references/prompt-location-patterns.md` - grep patterns for finding prompt construction sites per stack (Python, TS/JS, .NET, Java).
