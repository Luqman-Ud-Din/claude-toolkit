# Sandbox checklist by implementation

| Implementation | Verify |
|---|---|
| Subprocess (e.g. `subprocess.run` on generated code) | Restricted user/permissions, no network namespace access, timeout enforced, resource limits (`ulimit`/cgroups) set |
| Container-based (Docker/Firecracker per execution) | Ephemeral (destroyed after use), no mounted host volumes beyond a scratch dir, network policy denies egress unless explicitly needed, non-root user inside |
| WASM/restricted interpreter | Confirm the restriction is real (no `eval`/FFI escape path back to host), memory/instruction limits set |
| "Sandbox" that's actually the app's own process with `exec`/`eval` | Not a sandbox - treat as same-process execution (Critical) regardless of what it's called internally |

Whatever the implementation, ask: if the generated code were maximally
adversarial (assume it will try to escape), what's the actual worst case
given these controls? That answer is the Impact section of any finding here.
