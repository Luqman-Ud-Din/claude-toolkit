# Prompt quality checklist (per prompt)

- [ ] No internally contradictory instructions.
- [ ] No instruction vague enough to support two materially different readings.
- [ ] Consistent with any duplicated instruction elsewhere (no drift between copies of the "same" rule).
- [ ] Goal-based framing used where the task is genuinely variable; scripted steps used only where the task really is a fixed sequence.
- [ ] If structured output is expected: uses a provider structured-output/function-calling mode, not free-text-then-hope-and-parse.
- [ ] If free-text parsing is unavoidable: a documented fallback exists for malformed output (retry, default, explicit error - not a silent swallow or an unhandled crash).
- [ ] The model assigned to this step is proportionate to its actual difficulty/latency/cost requirements.
