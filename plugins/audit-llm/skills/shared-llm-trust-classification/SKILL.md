---
name: shared-llm-trust-classification
description: Rules for classifying every source that reaches an LLM's context window as trusted, semi-trusted, or untrusted - system/developer instructions, authenticated end-user input, retrieved documents, web pages, tool and API outputs, other agents' messages, memory, and file/image uploads. This is a shared building block, not run standalone - explore-llm-data-flow, audit-llm-prompt-injection, audit-llm-data-privacy-and-isolation, and audit-llm-intent-grounding-and-adaptability all classify sources the same way by calling this skill rather than inventing their own trust tiers. Use it whenever a skill needs to decide how much a piece of context should be allowed to influence model behavior, or whenever the user asks whether some input source is trusted.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Shared: LLM trust classification

Prompt injection findings, privacy findings, and intent-grounding findings all
turn on the same underlying question: *how much should this source be allowed
to change what the model does or says?* This skill fixes one answer to that
question so every skill that classifies a source agrees with every other one.

## The three tiers

| Tier | Definition | Can it introduce new instructions the model should follow? |
|---|---|---|
| **Trusted** | Authored by the application's developers and not reachable by any external party at request time: the system prompt, hard-coded tool definitions, config loaded from the deploy pipeline. | Yes - this is where instructions are supposed to come from. |
| **Semi-trusted** | Supplied by an authenticated party the application already has a trust relationship with, in the current turn: the logged-in user's own message, a value the user explicitly typed into a form. Also memory the same user previously wrote, if the storage is scoped so no one else can write to it. | Limited - can direct the conversation and select among the app's own capabilities, but should not be able to grant itself new tool access, change other users' data, or override the system prompt's constraints. |
| **Untrusted** | Anything that entered the context by being *fetched*, not *typed by the authenticated user this turn*: retrieved documents (RAG chunks), web pages, tool/API call results, file or image contents the user uploaded (until scanned - see note), other agents' messages in a multi-agent system, and any memory writable by a party other than its reader. | No - must be treated as data to reason about, never as instructions to follow, regardless of what it contains. |

## Edge cases that come up constantly

- **A user-uploaded file or screenshot** is semi-trusted for "the user wanted
  me to look at this" but its *contents* are untrusted the instant the model
  reads them - a PDF or image can carry embedded instructions the user never
  saw. Classify the upload event as semi-trusted, the extracted text/OCR as
  untrusted.
- **Tool output from a tool the app itself controls** (e.g. a database query
  your own backend runs) is still untrusted if the data underneath came from
  another user or an external system - the trust tier follows the data's
  origin, not the tool's ownership.
- **Memory / conversation history** is trusted at the tier of whoever wrote
  each entry, not a single tier for "memory" as a whole - a memory system
  that lets one tenant's content leak into another's context turns a
  semi-trusted source into an untrusted one; that gap is itself a finding
  (route it to `audit-llm-data-privacy-and-isolation`).
- **A message from another agent** in a multi-agent system is untrusted by
  default unless the receiving agent authenticates the sender and the
  message channel resists tampering - see `audit-llm-code-execution-and-multi-agent`.
- **System prompt built by concatenating trusted template + semi-trusted user
  profile fields** (name, preferences) is only as trusted as its most exposed
  concatenated part if that part is attacker-writable (e.g. a user-editable
  "bio" field spliced into the system prompt) - flag concatenation sites like
  this explicitly rather than calling the whole assembled prompt "trusted"
  because most of it came from a template.

## How consuming skills use this

- `explore-llm-data-flow` labels every source it maps with one of these three
  tiers plus a one-line justification.
- `audit-llm-prompt-injection` treats every untrusted source as a potential
  injection vector and checks the app enforces instruction/data separation at
  that boundary (structural separation - delimiters, separate message roles,
  tool-output tagging - not just an instruction telling the model to ignore
  embedded commands, which is not itself a control).
- `audit-llm-data-privacy-and-isolation` checks that untrusted-tier sources
  never get written into a trusted-tier location (e.g. a customer support
  transcript should never become part of the system prompt for other
  customers without explicit sanitization).

## Bundled files

- `references/classification-worksheet.md` - a fill-in table for tagging every source found during an explore-llm-data-flow pass.
