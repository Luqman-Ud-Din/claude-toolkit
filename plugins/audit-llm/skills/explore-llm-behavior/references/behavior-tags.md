# Behavioral tags

Use exactly one tag per probe result so runs are comparable over time:

| Tag | Meaning |
|---|---|
| `answered` | Responded substantively and appropriately to the request. |
| `refused` | Declined to fulfill the request, appropriately or not - note which in a comment. |
| `clarified` | Asked a clarifying question instead of guessing, for an ambiguous request. |
| `stated_limitation` | Correctly said a requested feature/capability doesn't exist or isn't supported. |
| `fabricated` | Answered as if a feature/fact exists when it does not, or invented specifics not grounded in real data. |
| `partial_compliance` | Did part of what was asked while declining or ignoring another part, without saying so. |
| `error` | The app returned an error/crash rather than any model response - note this is an app defect, not a model behavior. |

Add a one-line comment to any tag that isn't self-evidently good or bad in
context (e.g. `refused` on a genuinely out-of-scope request is correct;
`refused` on a normal request is not).
