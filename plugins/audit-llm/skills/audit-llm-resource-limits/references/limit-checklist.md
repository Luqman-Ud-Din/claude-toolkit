# Resource limit checklist

| Control | Present? | Evidence (file/config key) | Enforced where |
|---|---|---|---|
| Step/iteration cap | | | server-side loop, not model-reported |
| Token budget (per run) | | | |
| Token budget (per user/tenant/window) | | | |
| Cost budget with a hard stop | | | |
| Wall-clock timeout on the full run | | | |
| Per-user/tenant rate limit on starting new runs | | | |
| Loop/repetition detection (same tool+args repeated) | | | |
| Global cross-agent budget (multi-agent only) | | | |

For each row marked absent, state the concrete worst case: "a single
malicious or confused user could keep this agent looping indefinitely,
consuming provider spend with no ceiling" is a more useful Impact sentence
than "no resource limits found".
