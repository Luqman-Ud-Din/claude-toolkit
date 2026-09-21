---
name: explore-llm-architecture
description: Maps the control flow of an LLM/agentic application - single agent vs multi-agent, the orchestration loop (who decides the next step: code or the model), state handling across turns, and termination conditions (max steps, a stop tool, a judge call, or nothing) - and writes audit/llm/explore/explore-llm-architecture.json. Use it whenever the user asks how an AI agent or LLM feature is structured, wants an architecture diagram or walkthrough of an agent loop, asks whether something is single- or multi-agent, or asks which decisions are made by code versus delegated to the model - even when the user does not name this skill. Also runs as part of explore-llm-application and feeds audit-llm-excessive-agency, audit-llm-resource-limits, and audit-llm-code-execution-and-multi-agent.
---

## Plugin invocation

When invoking a skill from this bundle, use `audit-llm:<skill-name>`. Shared audit
utilities use `audit-core:<skill-name>`. Keep bare skill IDs in JSON, status files,
and output paths. Resolve `scripts/` and `references/` relative to this SKILL.md,
not the audited repository; quote script paths when running commands.


# Explore: LLM architecture

Produces a map, not findings - see design principle 4 in `llm-audit-skills.md`.
If something looks wrong while mapping (e.g. no visible termination condition),
note it in `open_questions` and flag which `audit-llm-*` skill should confirm
it as a finding; don't rate it yourself.

Prerequisites: `shared-llm-stack-detection`, `shared-llm-context-bootstrap`,
`shared-llm-handoff-contract` (all in this plugin).

## Workflow

1. **Bootstrap.** Call `shared-llm-context-bootstrap` for `audit/llm-stack.json`;
   if absent, run `shared-llm-stack-detection` first - you need to know which
   agent framework (if any) is in play before reading its control flow idiom.
2. **Find the entry point.** The place a request first reaches the model:
   an API route, a CLI command, a queue consumer, a scheduled job. There can
   be more than one (a chat endpoint and a background agent) - map each.
3. **Trace the loop.** For each entry point, answer:
   - Single call (one prompt, one response, done) or a loop (tool calls,
     re-prompting, multiple model turns)?
   - If a loop: who decides when to call which tool - a hard-coded sequence in
     code, or the model choosing from an offered tool list each turn?
   - **Termination**: a max-step/max-iteration cap, a dedicated "done" or
     "final_answer" tool, a judge/verifier call, a token/cost budget, or none
     of the above found? An agent with no visible termination condition is a
     real gap - record it precisely (file/line where the loop lives) so
     `audit-llm-resource-limits` can confirm and rate it.
   - **State**: is conversation/task state kept in-process (a variable, a
     class field), in a database keyed by session/user, or reconstructed from
     scratch each call from history passed by the caller? Note whether state
     is scoped per-user/per-tenant - `audit-llm-data-privacy-and-isolation`
     needs that answer, don't re-derive it there.
4. **Single vs multi-agent.** If more than one distinct agent/model role
   exists (a planner + executor, a router + specialists, agent-to-agent
   messaging), map each agent's role and how they hand off - that detail feeds
   `audit-llm-code-execution-and-multi-agent` directly and determines whether
   that skill runs at all.
5. **Write the map** to `audit/llm/explore/explore-llm-architecture.json`
   following `shared-llm-handoff-contract`'s explore envelope, with `items[].detail`
   shaped as:

   ```json
   {
     "entry_point": "POST /api/chat",
     "mode": "single-agent" ,
     "loop_control": "model-driven",
     "termination": {"type": "max_steps", "value": 8, "location": "src/agent/loop.py:40"},
     "state": {"storage": "postgres, keyed by session_id", "scoped_by": ["tenant_id", "user_id"]},
     "agents": []
   }
   ```

6. **Say what you couldn't resolve.** If the loop's termination condition, or
   whether it's model- or code-driven, isn't visible from source (e.g. it's
   configured entirely at runtime by an external orchestration platform),
   record that as an `open_questions` entry rather than guessing.

## Bundled files

- `references/architecture-patterns.md` - common agent-loop shapes per framework (LangGraph state machine, AutoGen group chat, CrewAI crew/process, a hand-rolled while-loop) and where each keeps its termination logic.
