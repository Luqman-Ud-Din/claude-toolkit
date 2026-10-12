#!/usr/bin/env python3
"""
signal_scan.py — deterministic pre-pass for expectations-analysis.

Pulls out the sentences in a requirements document that are most likely to
encode grading criteria, counts recurring evaluative themes, and lists any
mandated headings or fields. It finds candidates; it does not understand them.
Run it on long documents so nothing is lost to skimming, then do the real
reading.

Usage:
    python signal_scan.py <file> [--json]

Output sections:
    META SENTENCES     sentences about the exercise/evaluator/submission rather than the task
    THEME COUNTS       how often each evaluative theme recurs (repetition = weight)
    IMPERATIVES        communication verbs vs. build verbs (ratio hints at what is graded)
    MANDATED HEADINGS  headings/fields inside a required artifact (required-to-exist events)
    DELEGATIONS        sentences that hand a decision to the submitter
    REASSURANCES       "don't worry about X" lines (the deeper X is usually graded)
    OBSTACLE WARNINGS  "may be broken / existing codebase" lines (planted obstacles)
"""

import json
import re
import sys
from collections import Counter, OrderedDict

# --- Pattern tables ---------------------------------------------------------

META_PATTERNS = [
    r"\bwe (care|want|expect|'d like|would like|'re interested|are interested|'re looking|are looking|value|appreciate|prefer|'d rather|would rather)\b",
    r"\bwhat (we|they) (care|want|expect|look for|are looking for)\b",
    r"\b(tell|show|walk|explain|describe|note|flag|document|write .{0,20}down|let us know) (us|me|it|them|your|what|how|why)\b",
    r"\bpart of the (exercise|test|assessment|evaluation|interview)\b",
    r"\b(we|they) (don't|do not|won't|will not) (promise|guarantee|have|expect|need|require)\b",
    r"\bno (hidden|secret|right|wrong|correct) (checklist|answer|answers|rubric)\b",
    r"\b(expect|anticipate) (questions|to be asked|a discussion|follow-?up)\b",
    r"\bwe (may|might|will|'ll) (ask|go through|extend|discuss|review|read|look at|check)\b",
    r"\b(up to you|your call|we leave .{0,20} to you|make the (call|decision)|decide for yourself|at your discretion)\b",
    r"\b(timebox|time ?box|time limit|hours of|don't go (much )?over|please don't spend)\b",
    r"\b(use|using|used) ai\b|\b(claude|cursor|copilot|chatgpt|llm|gpt)\b",
    r"\b(raw|cleaned[- ]up|unedited|verbatim) (session|transcript|export|history)\b",
    r"\b(commit as you go|commit history|real history|squashed)\b",
    r"\b(treat it (like|as)|existing codebase|legacy|inherited|rough edges|may be broken|if .{0,30} (broken|fails|fights you))\b",
    r"\b(must|required|mandatory|shall)\b",
    r"\b(nice to have|optional|bonus|stretch)\b",
    r"\b(please (include|start|begin|mention|answer|use the word)|include the word|begin your (reply|proposal|response) with)\b",
    r"\b(long[- ]term|ongoing|partner|relationship)\b",
    r"\b(success metric|we'll know|we will know|measure success|kpi|north star)\b",
    r"\b(out of scope|non[- ]goals?|not in scope|explicitly excluded)\b",
    r"\b(open questions?|tbd|to be decided|undecided)\b",
    r"\b(evaluation criteria|scoring|weighted|points|rubric)\b",
    r"\b(how you (reason|think|approach|direct|work|communicate|decide|prioritize))\b",
    r"\b(trade[- ]?offs?|alternatives?|what you chose not to)\b",
]

THEMES = OrderedDict([
    ("reasoning / explain why", [r"\b(reason|reasoning|why|rationale|trade[- ]?off|judg(e)?ment|decide|decision|explain|justify)\b"]),
    ("ai direction", [r"\b(ai|claude|cursor|copilot|chatgpt|llm|gpt|prompt|prompts|session|transcript|direct them|steer)\b"]),
    ("scoping / time", [r"\b(timebox|time ?box|hours?|scope|fits? in the time|cut|defer|what you'd do next|next steps?|more time|didn't get to|did not get to)\b"]),
    ("communication / tell us", [r"\b(tell us|show us|walk us|let us know|note|write .{0,15}down|document|flag|explain|describe|write[- ]?up|notes?)\b"]),
    ("obstacles / existing codebase", [r"\b(broken|fix|work ?around|existing codebase|legacy|inherited|doesn't run|does not run|runs cleanly|rough edges|fights you)\b"]),
    ("process / history", [r"\b(commit|commits|history|git|pull request|pr\b|branch|squash)\b"]),
    ("code quality", [r"\b(clean code|code quality|readable|maintainable|tests?|test coverage|lint|style guide|best practices)\b"]),
    ("ui / design polish", [r"\b(ui|ux|design|polish|pixel|beautiful|responsive|animation)\b"]),
    ("correctness / completeness", [r"\b(complete|completeness|correct|correctness|working|works|bug[- ]free|edge cases?)\b"]),
    ("reliability / trust (client)", [r"\b(reliable|reliability|trust|burned|previous (freelancer|developer|vendor)|ghost|communication|availability|deadline)\b"]),
    ("compliance (rfp)", [r"\b(shall|mandatory|compliance|comply|page limit|format|deadline|submit by)\b"]),
    ("success metric (prd)", [r"\b(metric|kpi|success|measure|goal|outcome|impact|north star)\b"]),
])

COMM_VERBS = r"\b(tell|show|walk|explain|describe|note|flag|document|write|record|include|list|summarize|summarise|justify|report|mention|answer)\b"
BUILD_VERBS = r"\b(implement|build|add|create|develop|code|ship|deliver|integrate|deploy|write code|refactor|configure|set up|setup)\b"

DELEGATION_PATTERNS = [
    r"\b(up to you|your call|we leave .{0,25} to you|make the (call|decision)|decide for yourself|at your discretion|however you (like|prefer|see fit)|how you do (that|this|it) is up to you|not a spec|on purpose|wherever that happens)\b",
]
REASSURANCE_PATTERNS = [
    r"\b(don't worry|do not worry|no need to|you don't (have|need) to|doesn't count|does not count|don't count|do not count|hidden checklist|no (hidden|right|wrong|single|correct) (answer|answers|checklist|solution)|any (tools?|approach|language|stack) (is|are) fine|optional|not graded|we won't (judge|grade|penali[sz]e)|is plenty|is enough|it's enough|good enough)\b",
]
OBSTACLE_PATTERNS = [
    r"\b(don't promise|do not promise|may (not )?(run|work|build)|might (not )?(run|work|build)|broken|existing codebase|legacy|inherited|rough edges|fights you|runs cleanly|out of the box|you may need to)\b",
]

HEADING_LINE = re.compile(r"^\s*(#{1,6}\s+.+|[*_]{2}.+?[*_]{2}:?\s*(<.*>)?|[A-Z][A-Za-z ,/&'-]{2,60}:\s*$)")
TEMPLATE_PLACEHOLDER = re.compile(r"<[^<>]{2,60}>")


# --- Helpers ----------------------------------------------------------------

def split_sentences(text):
    text = re.sub(r"\r", "", text)
    # keep bullets as their own sentences
    text = re.sub(r"\n\s*[-*•]\s+", "\n", text)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z\"'(])|\n{1,}", text)
    return [p.strip() for p in parts if p and len(p.strip()) > 3]


def any_match(patterns, s):
    return any(re.search(p, s, re.I) for p in patterns)


COMMAND_LINE = re.compile(r"^\s*(cd|npm|npx|yarn|pnpm|pip|python3?|rails|bundle|git|docker|make|cargo|go|mvn|gradle|\./|export|source|cp|mv|rm|mkdir|curl|wget)\b")


def find_mandated_headings(text):
    """Lines that look like headings or fields inside a required artifact, and template placeholders.

    Skips '#' lines that sit among shell commands — those are code comments, not headings.
    """
    results = []
    lines = text.splitlines()
    in_artifact_block = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if re.search(r"\b(start from this|template|headings?|sections?|at the top|should (include|contain|cover)|must (include|contain|cover)|cover(ing)?:)\b", stripped, re.I):
            in_artifact_block = True
        if HEADING_LINE.match(stripped) and (in_artifact_block or stripped.startswith("#")):
            neighbours = [l for l in lines[max(0, i - 2):i] + lines[i + 1:i + 3]]
            if stripped.startswith("#") and any(COMMAND_LINE.match(n) for n in neighbours):
                continue  # shell comment inside a setup block
            results.append(stripped)
        for ph in TEMPLATE_PLACEHOLDER.findall(stripped):
            results.append(f"<placeholder> {ph}")
        if stripped == "" and in_artifact_block:
            # blocks usually end at a blank line; keep scanning though — be generous
            pass
    # also capture "covering X, Y, and Z" style enumerations
    for m in re.finditer(r"(cover(?:ing)?|including|covers)\s*:?\s*([^.\n]{10,200})", text, re.I):
        results.append(f"<enumerated> {m.group(2).strip()}")
    seen, out = set(), []
    for r in results:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


# --- Main -------------------------------------------------------------------

def scan(text):
    sentences = split_sentences(text)

    meta = [s for s in sentences if any_match(META_PATTERNS, s)]
    delegations = [s for s in sentences if any_match(DELEGATION_PATTERNS, s)]
    reassurances = [s for s in sentences if any_match(REASSURANCE_PATTERNS, s)]
    obstacles = [s for s in sentences if any_match(OBSTACLE_PATTERNS, s)]

    theme_counts = Counter()
    theme_hits = {k: [] for k in THEMES}
    for s in sentences:
        for theme, pats in THEMES.items():
            if any_match(pats, s):
                theme_counts[theme] += 1
                theme_hits[theme].append(s)

    # Count communication verbs only inside meta-sentences (instructions to the submitter
    # about reporting), and build verbs only outside them (the task itself). Counting across
    # everything lets setup instructions ("add members", "run install") swamp the signal.
    meta_set = set(meta)
    comm = sum(len(re.findall(COMM_VERBS, s, re.I)) for s in sentences if s in meta_set)
    build = sum(len(re.findall(BUILD_VERBS, s, re.I)) for s in sentences if s not in meta_set)

    headings = find_mandated_headings(text)

    return {
        "sentence_count": len(sentences),
        "meta_sentences": meta,
        "theme_counts": dict(theme_counts),
        "theme_hits": theme_hits,
        "imperatives": {"communication_verbs": comm, "build_verbs": build,
                         "ratio_comm_to_build": round(comm / build, 2) if build else None},
        "mandated_headings": headings,
        "delegations": delegations,
        "reassurances": reassurances,
        "obstacle_warnings": obstacles,
    }


def print_report(r):
    def section(title):
        print("\n" + "=" * 78)
        print(title)
        print("=" * 78)

    print(f"Sentences scanned: {r['sentence_count']}")

    section(f"META SENTENCES ({len(r['meta_sentences'])}) — candidates for rubric lines")
    for s in r["meta_sentences"]:
        print(f"  • {s}")

    section("THEME COUNTS — repetition is weight; zeros are informative")
    for theme in THEMES:
        print(f"  {r['theme_counts'].get(theme, 0):3d}  {theme}")

    section("IMPERATIVES — 'tell us' verbs in meta-sentences vs build verbs in task sentences")
    imp = r["imperatives"]
    print(f"  communication verbs (meta): {imp['communication_verbs']}")
    print(f"  build verbs (task):         {imp['build_verbs']}")
    print(f"  ratio comm:build:           {imp['ratio_comm_to_build']}")
    print("  (a ratio near or above 1.0 is unusual for a spec and suggests reporting/process is graded;")
    print("   treat as a hint, the meta-sentence list above is the real evidence)")

    section(f"MANDATED HEADINGS / FIELDS ({len(r['mandated_headings'])}) — required-to-exist events")
    for h in r["mandated_headings"]:
        print(f"  • {h}")

    section(f"DELEGATIONS ({len(r['delegations'])}) — decisions handed to you; rationale is graded")
    for s in r["delegations"]:
        print(f"  • {s}")

    section(f"REASSURANCES ({len(r['reassurances'])}) — the deeper version of X is usually graded")
    for s in r["reassurances"]:
        print(f"  • {s}")

    section(f"OBSTACLE WARNINGS ({len(r['obstacle_warnings'])}) — planted obstacles; notice, handle, report")
    for s in r["obstacle_warnings"]:
        print(f"  • {s}")

    print("\nThis is a candidate list. Interrogate each line with the nine questions; the script does not understand them.")


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    path = argv[1]
    as_json = "--json" in argv
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    result = scan(text)
    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print_report(result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
