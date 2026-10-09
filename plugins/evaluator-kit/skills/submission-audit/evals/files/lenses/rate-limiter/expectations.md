---
kind: evaluator-lens
version: 1
written: 2026-10-08
document: "Backend Engineering Exercise — Distributed Rate Limiter"
archetype: technical-take-home
brief: brief.md
context: context.md
veto: "The design reads as correct, but the load test couldn't have caught an over-admit, so you're asking us to take it on argument — which is exactly what burned us."
first_surface: README.md
---

# Evaluator Lens — Backend Engineering Exercise — Distributed Rate Limiter

**Doc type / evaluator / decision:** technical take-home · two engineers from a small infrastructure team, ~1 h each, behind a shared review handle · interview (the 45-minute call), then hire
**Filter or confirmation:** filter — the write-up decides whether the call happens; they hunt for the way the limiter could be wrong.

**Veto criterion:** "The design reads as correct, but the load test couldn't have caught an over-admit, so you're asking us to take it on argument — which is exactly what burned us." Their second-ranked value in their own words, one of the four "look closely" items, owner of RESULTS.md ("raw output"), the survivor of their fallback trade ("a correct limiter with a weak load test beats…"), and half the call's agenda ("design and results").

**Evaluator's mental model:**
"I own the gateway this sits in, and I've been paged for a limiter someone proved correct on a whiteboard. Every DESIGN.md says 'Lua script, atomic, done', so I open RESULTS.md and the load-test source first: real processes, one key, longer than a window — and would it have reported N+1? If the test has no teeth I don't trust the design section, however well written. The call is for the person who can say what their numbers don't prove."

## Implicit requirements
- The load test is graded as hard as the limiter: separate processes and connections, one contended key, longer than a window, bursty — "A load test where all clients share one connection is not a concurrency test." — **Stated**
- Correctness is their definition: never N+1 in *any rolling* 60-s window; over-rejecting is free, over-admitting disqualifies — "Over-rejecting is acceptable; over-admitting is not." — **Stated**
- The algorithm menu is a check: textbook token bucket and GCRA admit ~2N in a window from a full bucket, breaking requirement 3 as written — "Approximate algorithms are fine if you can show, with your load test, that they never over-admit." — **Strong**
- "What it doesn't guarantee" is a list: replication/failover loss, restart, Cluster slots, client timeouts — "explain what it guarantees and what it doesn't" — **Stated**
- The Redis-down call must square with the over-admit rule, be timeout-bounded (2 s unreachable ≠ 2 s per `allow()`), and be visible — "Fail open or fail closed? Tell us which you chose and why." — **Strong**
- Clock skew wants a yes/no and a number — "If so, how much skew breaks it?" — **Stated**
- AI use is examined on the call, not on paper: every line and number must be yours to defend — "We don't need to see prompts" + "a 45-minute call to go through your design and results" — **Strong**

## Rubric
| Criterion | Weight | Conf. | Failing looks like |
|---|---|---|---|
| Measured, not argued: test exercises the race and the window; raw output real; interpretation says what isn't proven | 30% | Stated | 20 goroutines, one pool, 30-second run, "max admitted: 100 ✓" |
| Never admits N+1 across processes (gate); race handling shown with non-guarantees | 25% | Stated | GET-then-SET; fixed window; "Lua is atomic, so it's correct" |
| Failure-mode judgment: Redis-down call squared with the invariant, timeout-bounded, visible; skew stated and quantified | 20% | Stated | "Fail open, it's fine"; "NTP handles it" |
| Decisions in one short paragraph each, their order, algorithm checked against the invariant | 10% | Stated | Three-page DESIGN.md; token bucket, no word on the 2N burst |
| Timebox and reproducibility: ≤4 h, honest "another 4 hours", README works from a clean clone (gate) | 8% | Stated | No cut list; README needs three undocumented steps |
| Latency reported with its environment, not optimized ahead of proof | 7% | Stated | Tuning section longer than correctness; a local cache |
| Code structure, unit tests, commit hygiene | tiebreaker | Inferred | — |

**Not graded (or tiebreaker only):** code elegance, unit tests, commit history, language, pluggable algorithms, an HTTP service around the library, dashboards (the losing side of their own trade), prompts (declined).
**Differentiators:** a falsification run — the same test against a deliberately racy build, reporting max > N; fault injection instead of prose — Redis paused 2 s and one process's clock skewed mid-run, outputs in RESULTS.md; the algorithm paragraph noting that the menu's rate-based options break their own invariant.

## What to show
| Criterion | Surface | Proof moment | Anti-pattern |
|---|---|---|---|
| Measured, not argued | README first lines → RESULTS.md → loadtest/ | Raw output: 3 processes × 8 workers, own connections, one key, 4 min with bursts, "max in any 60 s: 100 (N=100)"; naive build: max > N | One process, one pool, 30 s, many keys |
| Never admits N+1 + race handling | DESIGN.md §race; the .lua file | Script verbatim (trim, count, conditional add, expire), then "Guarantees:" / "Does not guarantee:" with ≥4 items | "Atomic, so correct"; MULTI/EXEC without WATCH |
| Failure-mode judgment | DESIGN.md §Redis-down, §clock-skew; RESULTS.md | "Fail closed after a 50 ms timeout, counter emitted — req 3's asymmetry decides it"; "No clock dependency: the script reads Redis TIME"; one run each | No timeout; "clocks are synced" |
| Decisions explained | DESIGN.md, four sections in their order | ≤150 words each, ending with the rejected alternative | A design essay |
| Timebox and reproducibility | README | "Time spent: 3h50"; prioritized "another 4 hours"; `git clone` → two commands, tested in an empty directory | "Everything's done"; untested README |
| Latency | RESULTS.md | p50/p99 with "localhost Docker, 24 clients; prod adds one RTT" | Tuning before proof |

**Required-to-exist events:**
- "DESIGN.md: algorithm choice" — chosen against the invariant, alternatives named — first 20 minutes, before code
- "DESIGN.md: race handling" — script and non-guarantees list exist — hour 1
- "DESIGN.md: Redis-down decision" — a call, a timeout, a 2-s pause run — hour 3
- "DESIGN.md: clock-skew analysis" — single-clock design or a numeric bound, plus a skewed run — hour 3
- "RESULTS.md: raw output" — ≥3 processes, ≥20 clients, one key, >60 s, pasted unedited — hour 3
- "RESULTS.md: interpretation" — what the numbers prove and don't — right after the run
- "What you'd do with another 4 hours" — a cut decided at the 2-hour mark, not the 4-hour mark
- "README from a clean checkout" — a fresh clone actually run — last 15 minutes

**Simulated verdict (if the plan is followed):** "Ran real processes on one key past a window boundary, hit N exactly, and broke their own limiter to show the test would catch it; the design section says what the script doesn't guarantee. Set up the call."
**Simulated verdict (if read as a feature spec — clean limiter, well-argued DESIGN.md, a quick load test):** "The script looks right and the write-up is good, but the test ran one process on a pool for thirty seconds and never crossed a window — we'd be taking it on faith, which is the one thing we said we won't do."

---

## Explicit requirements
- [MUST] Library, single entry point `allow(key) -> bool`; per-key N per rolling 60-s window; correct across instances and processes — "never admits request N+1 inside any 60-second window"; over-reject acceptable, over-admit not.
- [MUST] Redis as the shared store, via the docker-compose.yml in their repo.
- [MUST] Load test: ≥20 concurrent clients, ≥3 limiter processes; reports (a) max admitted in any 60-s window for a single key and (b) p50/p99 of `allow()`.
- [MUST] RESULTS.md — raw load-test output plus a short interpreting paragraph.
- [MUST] DESIGN.md — four sections, "one short section each", in this order: algorithm choice (which and why, "in a paragraph"); race handling (if Lua or MULTI/EXEC, show the script, explain what it guarantees and doesn't); Redis unreachable 2 s (open or closed, which and why); clock skew (dependency yes/no, how much breaks it).
- [MUST] README.md — run the limiter and the load test "from a clean checkout".
- [MUST] "Tell us what you'd do with another 4 hours" — no file is named for it; put it in README.
- [MUST] Private GitHub repo; invite @nw-platform-review.
- [MUST] "Please spend no more than 4 hours" — a timebox in polite clothing; writing counts, no exemption is offered.
- [SHOULD] The load test is a real concurrency test — not one shared connection.
- [MAY] Any language (they use Go and Python); any tools including AI, prompts not wanted; any algorithm; approximate algorithms if the load test shows no over-admit.
- Mechanics: review within a week, then a 45-minute call with two engineers on "design and results".

## Traps
- **"Rolling" rules out the easy implementation.** A fixed-window counter admits up to 2N across a boundary. Planted by one word in the first paragraph.
- **The algorithm menu contains algorithms that violate requirement 3.** Token bucket (capacity N, refill N/60) and GCRA with burst N both admit ~2N in a 60-s window starting from a full bucket; the two-bucket sliding-window counter can over-admit on edge bursts. "Approximate… if you can show… they never over-admit" is the tell. Sliding log (a sorted set of timestamps) is the only listed option whose admit set equals the invariant; if you pick an approximation, bias it to over-reject and say so.
- **MULTI/EXEC is named so they can see whether you know it is not a read-modify-write primitive.** Commands are queued; you cannot branch on a read inside it. WATCH + retry is optimistic and livelocks with 20 clients on one key. Lua is the answer; say in one line why MULTI/EXEC isn't.
- **INCR then EXPIRE as two commands.** A crash between them leaves a key that never expires. Keep everything in one script.
- **TIME inside Lua.** Reading TIME and then writing needs effects replication — default since Redis 5, the only mode in 7; older servers need `redis.replicate_commands()` first. Pin the Redis image if their compose doesn't, and mention it under non-guarantees. An evaluator who has hit this will notice you did.
- **Load-test shapes that pass without testing anything:** threads instead of processes (they said processes); one shared connection or pool; load spread over many keys (no contention); a run shorter than 60 s (the window never rolls); steady-state only (the race surfaces under bursts at window edges, and token-bucket over-admit only after idle); N set so high it is never reached (the test "passes" with zero rejections); max-in-window computed over fixed 60-s buckets instead of any 60-s window (sort admit timestamps, two-pointer sweep).
- **Latency "optimizations" that break correctness.** Any instance-local cache, pre-check, or batched `allow()` over-admits across instances. If they see one, the call starts there.
- **Over-delivery:** a dashboard (named as the losing side of their own trade), an HTTP service around the library, pluggable algorithms, Redis Cluster support, multi-language ports, a PROMPTS.md (declined).
- **Blocks review entirely:** a public repo (leaks their exercise); the wrong handle; the three files not at the root with those exact names; a README that fails from a clean clone — then RESULTS.md is unverifiable and the whole submission becomes "argued".
- **"The repo."** "A docker-compose.yml with Redis is in the repo" means a starter repo exists. This project folder has only EXERCISE.txt. Confirm you have the starter; build inside it and keep their compose file.
- **Register:** terse, numbered, engineering. Short sections and numbers; no selling.

## Decisions to make / questions to ask
No Q&A channel is offered; decide and write it down.
- Algorithm → sliding log: ZSET of request timestamps, one Lua script — "Only listed option whose admit set exactly matches 'never more than N in any 60-s window'; O(N) memory per key is the cost and is fine at API-key scale; token bucket/GCRA admit up to ~2N from a full bucket."
- Window semantics → half-open (now − 60 000 ms, now], millisecond resolution, Redis TIME — "State it; 'any 60-second window' is ambiguous at the boundary."
- Race → single Lua script: ZREMRANGEBYSCORE, ZCARD, conditional ZADD, PEXPIRE — "Atomic per key on one Redis node. Does not guarantee: survival of async replication/failover; restart without persistence; cross-slot keys in Cluster; anything if the client times out after the script already ran."
- Redis unreachable 2 s → fail closed, 50 ms connect+read timeout, no in-path retry, counter/log emitted; `on_error` configurable, closed by default — "Requirement 3's asymmetry and 'false confidence is worse than no limiter' decide it. Fail-open's cost, stated: rate × 2 s uncounted admits, and an under-counted window for the next 60 s." (Fail-open is defensible if you argue public-API availability outranks the limit; write it as an explicit exception to requirement 3, not a default.)
- Clock skew → none: Redis's clock is the only clock — "Instance clocks are never read. Residual: a failover to a replica with a different clock shifts the window once. If client clocks were used, over-admit ≈ N × δ/60 for skew δ."
- N and window → constructor parameters; test at N=100, 60 s — "Choose N so the test saturates: 24 clients at ~50 req/s ≫ N/60."
- Load-test shape → 3 OS processes × 8 workers, own connection each, one key, 4 min (burst / steady / idle / burst), plus `--impl naive` — "The naive run is what proves the test can fail."
- Latency → wall-clock around `allow()` per call, pooled p50/p99 — "Report the environment: localhost Docker; prod adds one RTT."
- Where "another 4 hours" lives → README, prioritized: failover/replication behavior, Cluster hash tags, memory bound for sliding log, multi-key mix, real-network latency, chaos tests.
- Language → Python (redis-py, multiprocessing) or Go; whichever you write fastest — "Not graded; they read both."

## Recommended shape
Four hours, in the order the evaluator reads and the proportion they weigh.
| Section (in reading order) | Share | Carries |
|---|---|---|
| Decide: algorithm, window semantics, script on paper; open a decisions scratch file | 0:00–0:20 | Algorithm paragraph written against the invariant |
| Limiter: client with timeout, Lua script, `allow()` fail-closed on error (~80 lines) | 0:20–1:00 | The script, verbatim, for DESIGN.md |
| Load test: ≥3 processes, own connections, one key, >60 s with bursts; sliding max-in-window + p50/p99 post-processor; `--impl naive` | 1:00–2:15 | The veto proof |
| Cut-list checkpoint | 2:15–2:30 | "Another 4 hours" |
| Runs: main, naive, Redis paused 2 s, one process's clock +30 s; capture raw | 2:30–3:10 | RESULTS.md raw; Redis-down and skew sections with data |
| DESIGN.md (4 × ≤150 words), RESULTS.md (raw + one paragraph), README (headline numbers in the first 3 lines, two commands, time spent, next 4 hours) | 3:10–3:50 | Every mandated heading populated |
| Fresh clone test; private repo; invite @nw-platform-review | 3:50–4:00 | Review can happen |

Repo in reading order: README.md → RESULTS.md → loadtest/ → DESIGN.md → limiter/ (with the `.lua` as its own file) → their docker-compose.yml.

## Pre-submission check
- [ ] Every required artifact present and populated with what its name promises: README, DESIGN (4 sections, their order), RESULTS (raw + interpretation), "another 4 hours"
- [ ] Veto-criterion proof is on the first surface the evaluator reads: README's first lines carry max-in-window vs N, processes × clients × duration, and the naive build's failure
- [ ] Every primary criterion has at least one quotable proof moment
- [ ] Load test: separate OS processes, own connections, one key, >60 s, bursts, N reachable; max-in-window is a sliding computation
- [ ] DESIGN §race lists what the script does **not** guarantee (≥4 items)
- [ ] DESIGN §Redis-down names the timeout and what the caller sees; §clock-skew gives yes/no and a number
- [ ] RESULTS paragraph states the environment and what the run does not prove
- [ ] No dashboard, HTTP wrapper, local cache, or PROMPTS.md
- [ ] Time spent stated and ≤4 h
- [ ] Repo private, @nw-platform-review invited, files at root with exact names; README tested from `git clone` into an empty directory
- [ ] You can explain every line of the Lua script and every number in RESULTS.md without notes — the call is 45 minutes on exactly those two things

**Sequencing:** before starting — algorithm chosen against the invariant, decisions file open; first third — script and non-guarantees written; halfway — cut list decided; last third — four runs captured raw, write-ups; after work — fresh-clone test, private repo, invite.

**Saved to:** `docs/evaluator-expectations/` — brief.md · context.md · expectations.md (and `.gitignore` updated)
