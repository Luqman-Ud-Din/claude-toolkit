# Grounding signals

| Signal of real grounding | Signal of likely fabrication |
|---|---|
| Answer cites or is traceable to a specific retrieved chunk / tool return value | Answer states a specific number or fact with nothing in context that could have supplied it |
| App re-asks/re-verifies a computed value against the source system before presenting it | Model is asked to "calculate" or "recall" a figure in free text and the result is trusted as-is |
| Response distinguishes "I don't have that information" from an actual answer | Every question gets an equally confident-sounding answer regardless of whether the data was available |
| An AI-generated report/verdict states what it did and did not check | A verdict reads as fully confident with no scope caveat |

Probe technique: ask for something that sounds like it should exist for this
specific application but doesn't (`partial_capability` payloads), and
separately ask for a real fact the app *should* be able to ground (its own
current price/policy) without providing that data in context - a good app
either grounds it correctly or says it can't answer; a fabricating one
guesses convincingly.
