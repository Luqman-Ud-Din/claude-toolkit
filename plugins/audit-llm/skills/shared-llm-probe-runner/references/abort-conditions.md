# Abort conditions

Stop the probe run immediately, and tell the user, when any of these happen:

- **A test account gets locked or flagged.** Continuing risks it affecting a
  real support queue or fraud system. Report which probe preceded the lock.
- **The target starts returning content that suggests a real side effect
  fired** (a real email/SMS confirmation, a real payment reference) when the
  probe was meant to stay dry-run. Stop and tell the user which probe to
  check/undo.
- **Sustained 429/503s** beyond the single 10s backoff the script already
  does - the target's rate limiting is engaging harder than expected; ask
  before increasing `--min-interval` and retrying rather than hammering it.
- **The application's owner (if different from the requester) has not
  confirmed the test window** - if this surfaces mid-run, stop; a probe run
  someone else didn't expect can look identical to an attack from the
  receiving end.
- **A probe appears to have caused actual harm** (real data changed, a real
  notification sent to a real customer) - stop, document exactly what
  happened and when, and tell the user immediately so they can remediate;
  do not keep probing to "confirm" the impact.

None of these are the calling skill's job to detect mid-request - they are why
`probe_runner.py` logs every response as it happens rather than batching
output at the end: a human (or the calling skill, reading incrementally) can
catch one of these before the whole probe list finishes.
