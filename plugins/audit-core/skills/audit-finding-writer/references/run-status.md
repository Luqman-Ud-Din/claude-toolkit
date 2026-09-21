# Audit run status

Finding-producing conventional audit skills write `audit/status/<skill>.json`:

```json
{
  "skill": "<bare skill-name>",
  "status": "completed|failed|skipped",
  "reason": "...",
  "started_at": "...",
  "finished_at": "..."
}
```

Choose one status value, record the actual timestamps, and explain failures or skips.
Keep the skill ID unnamespaced; plugin namespaces are for invocation only.
Infrastructure helpers do not acquire status files just because they are packaged
in audit-core. The audit-application orchestrator remains the owner of run state.
