# Eval maturity ladder

| Level | Description | Typical severity of "we're at this level" finding |
|---|---|---|
| 0 - None | No eval set, no red-team pass, changes ship on vibes | High |
| 1 - Manual spot-check | Someone tries a few prompts by hand before releasing | Medium-High |
| 2 - Static eval set | A fixed set of prompt/expected-output pairs exists but isn't adversarial and isn't gated in CI | Medium |
| 3 - Gated CI | Eval set runs automatically and blocks merge/deploy on failure, but coverage is happy-path only | Low-Medium |
| 4 - Adversarial + gated | Eval set includes paraphrase/injection/jailbreak/partial-capability cases from the payload library, runs in CI, and is updated from confirmed audit findings | Informational (this is the target state) |

State the app's level explicitly in the finding and cite what's missing to
reach the next level - a specific, incremental Remediation beats "add more
tests".
