#!/usr/bin/env python3
"""Duplicate code block finder: normalised lines + Rabin-Karp rolling hash over
windows of --min-lines, extended to maximal blocks and grouped into clone sets.

Usage:
    python duplicates.py <repo_root> [--min-lines 6] [--min-chars 80] [--ignore-identifiers]
                         [--exclude GLOB ...] [--top 50] [--out duplicates.json] [--md duplicates.md]

Normalisation (per line, after comments and string contents are blanked):
  * all whitespace removed; numeric literals -> N; string contents already blank, so
    "invoice" and "quote" compare equal (near-identical code differing only in literals);
  * --ignore-identifiers additionally replaces every non-keyword identifier with I
    (catches renamed-variable clones, like PMD CPD --ignore-identifiers; noisier);
  * trivial lines are dropped before windowing: blank, lone braces/brackets, else, try,
    finally, break;, return;, and using / import / package / namespace lines.
A clone is a run of >= --min-lines normalised lines (and >= --min-chars characters)
appearing at two or more places. Each occurrence names its enclosing function (via
complexity.py) and "function_clone": true when the block covers >= 60% of that
function's lines - that is the "two near-identical functions" case.
duplication_pct = duplicated normalised lines / all normalised lines x 100.
Test files are included (duplicated test setup is debt too) but flagged. Generated and
vendored paths are skipped as in complexity.py. Read-only against the audited repo.
"""
import argparse
import fnmatch
import json
import os
import re
import sys
import zlib
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import complexity  # noqa: E402

MOD = (1 << 61) - 1
BASE = 1_000_003
TRIVIAL = {"", "{", "}", "};", "});", ")", "(", "];", "]", "[", "else", "try", "finally", "break;", "return;",
           "continue;", "end", "pass", "});});", "})", "},", "),", "</div>", "<div>", "default:", "#endregion"}
TRIVIAL_START = ("using", "import", "package", "namespace", "from", "#region", "export*from", "@use", "@import")
KEYWORDS = {"if", "else", "for", "foreach", "while", "do", "switch", "case", "default", "break", "continue", "return",
            "try", "catch", "finally", "throw", "new", "var", "let", "const", "function", "class", "public", "private",
            "protected", "internal", "static", "async", "await", "void", "int", "string", "bool", "decimal", "double",
            "float", "long", "true", "false", "null", "this", "base", "super", "def", "elif", "except", "raise",
            "and", "or", "not", "in", "is", "None", "True", "False", "self", "import", "from", "as", "with", "yield",
            "lambda", "readonly", "override", "virtual", "abstract", "interface", "enum", "struct", "record", "out",
            "ref", "typeof", "instanceof", "of", "get", "set", "value", "undefined"}
NUM_RE = re.compile(r"\b\d+(?:\.\d+)?[mMfFdDlLuU]?\b")
IDENT_RE = re.compile(r"\b[A-Za-z_]\w*\b")
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)|\.(spec|test)\.|Tests?\.cs$|_test\.py$|(^|/)test_[^/]*\.py$", re.I)


def normalise(stripped_text, ignore_identifiers):
    out = []
    for n, raw in enumerate(stripped_text.split("\n"), 1):
        s = re.sub(r"\s+", "", raw)
        if s in TRIVIAL or s.startswith(TRIVIAL_START) or len(s) < 3:
            continue
        s = NUM_RE.sub("N", s) if not ignore_identifiers else s
        if ignore_identifiers:
            s = NUM_RE.sub("N", IDENT_RE.sub(lambda m: m.group(0) if m.group(0) in KEYWORDS else "I",
                                             re.sub(r"\s+", " ", raw).strip()))
            s = re.sub(r"\s+", "", s)
        out.append((s, n))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    ap.add_argument("--min-lines", type=int, default=6)
    ap.add_argument("--min-chars", type=int, default=80)
    ap.add_argument("--ignore-identifiers", action="store_true")
    ap.add_argument("--exclude", action="append", default=[])
    ap.add_argument("--top", type=int, default=50)
    ap.add_argument("--max-bucket", type=int, default=50, help="cap occurrences examined per hash bucket")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args()
    w = a.min_lines

    docs = []  # (rel, normalised lines, analysis)
    for full, rel in complexity.iter_code_files(a.root, a.exclude):
        try:
            with open(full, "r", encoding="utf-8", errors="ignore") as fh:
                text = fh.read()
        except OSError:
            continue
        ext = os.path.splitext(full)[1].lower()
        if ext == ".vue":
            text, _ = complexity.vue_script(text)
            if text is None:
                continue
        stripped = complexity.strip_python(text) if ext == ".py" else complexity.strip_c_like(text)
        docs.append((rel, normalise(stripped, a.ignore_identifiers), full))

    buckets = defaultdict(list)
    power = pow(BASE, w - 1, MOD)
    for di, (_, norm, _) in enumerate(docs):
        if len(norm) < w:
            continue
        hs = [zlib.crc32(s.encode("utf-8")) + 1 for s, _ in norm]
        h = 0
        for k in range(w):
            h = (h * BASE + hs[k]) % MOD
        buckets[h].append((di, 0))
        for i in range(1, len(norm) - w + 1):
            h = ((h - hs[i - 1] * power) * BASE + hs[i + w - 1]) % MOD
            buckets[h].append((di, i))

    def same(d1, i1, d2, i2):
        n1, n2 = docs[d1][1], docs[d2][1]
        if i1 < 0 or i2 < 0 or i1 >= len(n1) or i2 >= len(n2):
            return False
        return n1[i1][0] == n2[i2][0]

    groups = {}
    covered = defaultdict(set)
    for occ in buckets.values():
        if len(occ) < 2:
            continue
        occ = occ[:a.max_bucket]
        for x in range(len(occ)):
            for y in range(x + 1, len(occ)):
                (d1, i1), (d2, i2) = occ[x], occ[y]
                if d1 == d2 and abs(i1 - i2) < w:
                    continue
                if not all(same(d1, i1 + k, d2, i2 + k) for k in range(w)):
                    continue  # hash collision
                if same(d1, i1 - 1, d2, i2 - 1) and not (d1 == d2 and abs(i1 - i2) <= w):
                    continue  # continuation of a longer match found from an earlier window
                L = w
                while same(d1, i1 + L, d2, i2 + L) and not (d1 == d2 and i1 + L >= i2 > i1):
                    L += 1
                block = tuple(s for s, _ in docs[d1][1][i1:i1 + L])
                if sum(len(s) for s in block) < a.min_chars:
                    continue
                key = zlib.crc32("\n".join(block).encode("utf-8"))
                g = groups.setdefault(key, {"lines": L, "occ": set(), "sample": block[:3]})
                g["occ"].add((d1, i1, L))
                g["occ"].add((d2, i2, L))

    analyses = {}
    clones = []
    for g in groups.values():
        occs = []
        for di, i, L in sorted(g["occ"]):
            rel, norm, full = docs[di]
            start, end = norm[i][1], norm[i + L - 1][1]
            for k in range(i, i + L):
                covered[di].add(k)
            if rel not in analyses:
                analyses[rel] = complexity.analyze_file(full, rel)
            fn = complexity.function_at({rel: analyses[rel]["functions"]} if analyses[rel] else {}, rel, start)
            occs.append({"file": rel, "start": start, "end": end,
                         "function": fn["name"] if fn else None,
                         "function_clone": bool(fn and (end - start + 1) >= 0.6 * fn["length"]),
                         "test_code": bool(TEST_RE.search(rel))})
        clones.append({"lines": g["lines"], "occurrences": occs, "sample": list(g["sample"]),
                       "function_clone": sum(o["function_clone"] for o in occs) >= 2})
    # drop clone groups fully contained in a larger group at the same places
    clones.sort(key=lambda c: (-c["lines"], -len(c["occurrences"])))
    kept = []
    for c in clones:
        inside = False
        for k in kept:
            if all(any(o["file"] == p["file"] and p["start"] <= o["start"] and o["end"] <= p["end"] for p in k["occurrences"])
                   for o in c["occurrences"]):
                inside = True
                break
        if not inside:
            kept.append(c)

    total = sum(len(d[1]) for d in docs)
    dup = sum(len(v) for v in covered.values())
    result = {"root": os.path.abspath(a.root), "min_lines": w, "min_chars": a.min_chars,
              "mode": "ignore-identifiers" if a.ignore_identifiers else "literals-normalised",
              "files": len(docs), "total_lines": total, "duplicated_lines": dup,
              "duplication_pct": round(dup * 100.0 / total, 2) if total else 0.0,
              "clone_groups": len(kept), "function_clones": sum(1 for c in kept if c["function_clone"]),
              "clones": kept[:a.top] if a.top > 0 else kept}
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
    if a.md:
        os.makedirs(os.path.dirname(os.path.abspath(a.md)) or ".", exist_ok=True)
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("Duplication: %.2f%% (%d of %d normalised lines), %d clone groups\n\n"
                     % (result["duplication_pct"], dup, total, len(kept)))
            fh.write("| Lines | Occurrences | Function clone |\n|---|---|---|\n")
            for c in result["clones"]:
                locs = "<br>".join("`%s:%d-%d` %s" % (o["file"], o["start"], o["end"], o["function"] or "") for o in c["occurrences"])
                fh.write("| %d | %s | %s |\n" % (c["lines"], locs, "yes" if c["function_clone"] else ""))
    print(json.dumps({"duplication_pct": result["duplication_pct"], "clone_groups": len(kept),
                      "top": [" ~ ".join("%s:%d(%s)" % (o["file"], o["start"], o["function"]) for o in c["occurrences"])
                              for c in kept[:5]]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
