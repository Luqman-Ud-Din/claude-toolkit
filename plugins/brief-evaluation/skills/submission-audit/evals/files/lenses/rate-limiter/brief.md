Backend Engineering Exercise — Distributed Rate Limiter

Hi, and thanks for your interest in the Platform team at Northwind.

What you'll build

Our public API is fronted by a fleet of 12 gateway instances behind a load balancer. We need a rate limiter that enforces a per-API-key limit of N requests per rolling 60-second window, correctly, across all instances. A key must never be allowed more than N requests in any 60-second window, regardless of which instances the requests land on or how they are timed.

Requirements

1. Implement the limiter as a library with a single entry point: allow(key) -> bool.
2. Use Redis as the shared store. A docker-compose.yml with Redis is in the repo.
3. The limiter must be correct under concurrent access from multiple processes. "Correct" means: never admits request N+1 inside any 60-second window for a key. Over-rejecting is acceptable; over-admitting is not.
4. Include a load test that runs at least 20 concurrent clients against at least 3 limiter processes and reports (a) the maximum number of requests admitted in any 60-second window for a single key, and (b) p50 / p99 latency of allow().
5. Include the raw output of your load test in RESULTS.md, plus a short paragraph interpreting it.

What we're evaluating

We are a small infrastructure team and this limiter would sit in the hot path of every request we serve. Correctness under concurrency is the thing we care most about — a limiter that is fast but occasionally admits N+1 is worse than no limiter, because it gives us false confidence. Second to that, we care about whether you measured rather than reasoned: we have been burned by designs that were argued correct and were not. Third, we care about latency, but only once the first two hold.

Things that are fine

- Use any language you're comfortable in. We use Go and Python; neither is required.
- Use whatever tools you normally use, including AI assistants. We don't need to see prompts.
- Pick any algorithm (sliding log, sliding window counter, token bucket, GCRA). Tell us which and why in a paragraph.
- Approximate algorithms are fine if you can show, with your load test, that they never over-admit.

Things we'll look at closely

- How you handle the race between read and write on the counter. If your answer is "Lua script" or "MULTI/EXEC", show us the script and explain what it guarantees and what it doesn't.
- What happens when Redis is unreachable for 2 seconds. Fail open or fail closed? Tell us which you chose and why.
- Clock skew between instances. Does your design depend on instance clocks agreeing? If so, how much skew breaks it?
- Whether your load test actually exercises the race. A load test where all clients share one connection is not a concurrency test.

Time

Please spend no more than 4 hours. If you run out of time, a correct limiter with a weak load test beats a fast limiter with a beautiful dashboard. Tell us what you'd do with another 4 hours.

Submission

Push to a private GitHub repo and invite @nw-platform-review. Include:
- README.md: how to run the limiter and the load test from a clean checkout
- DESIGN.md: algorithm choice, the race handling, the Redis-down decision, the clock-skew analysis — one short section each
- RESULTS.md: raw load test output and your interpretation

We review within a week and will schedule a 45-minute call to go through your design and results with two of our engineers.
