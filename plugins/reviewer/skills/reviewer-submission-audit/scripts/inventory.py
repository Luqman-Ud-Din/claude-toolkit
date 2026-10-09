#!/usr/bin/env python3
"""
inventory.py — deterministic inventory of a submission for reviewer-submission-audit.

Lists files with sizes and types, word-counts text files, summarises a git log if
present, flags leftover placeholders, and (with --transcript) counts human turns
and short-approval turns in an AI session export. It finds; the auditor interprets.

Usage:
    python inventory.py <path> [--transcript <file>] [--mandated name1,name2,...] [--json]

<path> may be a directory, a repository root, or a single file.

Sections:
    FILES         path · bytes · kind · words (text only)
    REPOSITORY    commit count, span, median message length, timestamps
    MANDATED      which of the --mandated names exist (case-insensitive, any depth)
    PLACEHOLDERS  file:line with <…>, TODO, TBD, lorem, {{…}}, FIXME, XXX
    TRANSCRIPT    human turns, short-approval turns, ratio, direction-word turns
"""

import json
import os
import re
import statistics
import subprocess
import sys
from datetime import datetime

TEXT_EXT = {".md", ".txt", ".rst", ".csv", ".json", ".yaml", ".yml", ".toml", ".ini",
            ".py", ".rb", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
            ".swift", ".c", ".h", ".cpp", ".cs", ".sh", ".sql", ".html", ".css", ".xml",
            ".tex", ".org", ".ipynb"}
DOC_EXT = {".docx": "word", ".xlsx": "excel", ".xlsm": "excel", ".pptx": "slides",
           ".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image",
           ".gif": "image", ".svg": "image", ".mp4": "video", ".mov": "video",
           ".webm": "video", ".mp3": "audio", ".wav": "audio", ".zip": "archive",
           ".tar": "archive", ".gz": "archive"}
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".next", "dist",
             "build", ".idea", ".vscode", "vendor", "target", ".pytest_cache"}

PLACEHOLDER_PATTERNS = [
    (r"<[a-zA-Z][^<>]{1,60}>", "angle-placeholder"),
    (r"\{\{[^}]{1,60}\}\}", "curly-placeholder"),
    (r"\bTODO\b", "TODO"),
    (r"\bTBD\b", "TBD"),
    (r"\bFIXME\b", "FIXME"),
    (r"\bXXX\b", "XXX"),
    (r"\blorem ipsum\b", "lorem"),
    (r"\[insert[^\]]*\]", "insert-placeholder"),
    (r"\byour name\b", "your-name"),
]
# angle placeholders inside code/html are usually tags; only flag in prose-like files
PLACEHOLDER_FILES = {".md", ".txt", ".rst", ".org"}

SHORT_APPROVAL = re.compile(
    r"^\s*(ok(ay)?|yes|yep|yeah|sure|continue|go ahead|go on|proceed|next|do (it|that)|"
    r"looks good|lgtm|sounds good|great|perfect|fine|good|thanks|thank you|that works|"
    r"please (continue|proceed|do)|carry on|keep going|yes please|do that|ok go|k)\s*[.!]*\s*$",
    re.I)
DIRECTION_WORDS = re.compile(
    r"\b(no[,.]|don't|do not|instead|rather|not that|wrong|incorrect|revert|undo|stop|"
    r"drop|cut|skip|remove|out of scope|constraint|must|never|the brief says|"
    r"because|why|rejected|push ?back|change (direction|approach)|actually|wait)\b", re.I)


def kind_of(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in TEXT_EXT:
        return "text"
    return DOC_EXT.get(ext, "other")


def word_count(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return len(f.read().split())
    except OSError:
        return None


def walk_files(root):
    if os.path.isfile(root):
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        # the handoff folders are the audit's inputs/outputs, not part of the submission
        if os.path.basename(dirpath) == "docs":
            dirnames[:] = [d for d in dirnames if d not in ("reviewer-requirements", "submission-audit")]
        for fn in sorted(filenames):
            yield os.path.join(dirpath, fn)


def git_summary(root):
    if not os.path.isdir(os.path.join(root, ".git")):
        return None
    try:
        out = subprocess.run(
            ["git", "-C", root, "log", "--format=%h%x09%aI%x09%s", "--date=iso"],
            capture_output=True, text=True, check=True).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    if not out:
        return {"commits": 0}
    rows = [line.split("\t", 2) for line in out.splitlines()]
    times = []
    for r in rows:
        try:
            times.append(datetime.fromisoformat(r[1]))
        except ValueError:
            pass
    msgs = [r[2] for r in rows if len(r) > 2]
    span_hours = None
    if len(times) >= 2:
        span_hours = round(abs((max(times) - min(times)).total_seconds()) / 3600, 2)
    weak = [m for m in msgs if re.match(r"^(wip|fix|fixes|update|updates|changes|stuff|misc|more|tweak|typo)\b", m.strip(), re.I)]
    intent = [m for m in msgs if re.search(r"\b(because|so that|instead of|rather than|not just|enforce|revert|drop|cut)\b", m, re.I)]
    now = datetime.now().astimezone()
    future = [t.isoformat() for t in times if t > now]
    # handoff folders or secrets tracked in history — a reviewer would see them
    try:
        tracked = subprocess.run(["git", "-C", root, "ls-tree", "-r", "HEAD", "--name-only"],
                                 capture_output=True, text=True, check=True).stdout.splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError):
        tracked = []
    should_not_track = [p for p in tracked if re.search(
        r"(^|/)docs/(reviewer-requirements|submission-audit)/|(^|/)\.env($|\.)|(^|/)(id_rsa|\.npmrc|\.pypirc)$|secret|credential", p, re.I)]
    return {
        "commits": len(rows),
        "first": min(times).isoformat() if times else None,
        "last": max(times).isoformat() if times else None,
        "span_hours": span_hours,
        "future_dated_commits": future,
        "median_message_chars": int(statistics.median(len(m) for m in msgs)) if msgs else 0,
        "weak_messages": len(weak),
        "intent_messages": len(intent),
        "tracked_but_should_not_be": should_not_track,
        "log": [{"hash": r[0], "time": r[1], "subject": r[2] if len(r) > 2 else ""} for r in rows],
    }


def find_placeholders(path):
    ext = os.path.splitext(path)[1].lower()
    hits = []
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                for pat, name in PLACEHOLDER_PATTERNS:
                    if name == "angle-placeholder" and ext not in PLACEHOLDER_FILES:
                        continue
                    if re.search(pat, line, re.I):
                        hits.append({"file": path, "line": i, "kind": name, "text": line.strip()[:120]})
                        break
    except OSError:
        pass
    return hits


def transcript_stats(path):
    """Heuristic turn splitter for common exports. Returns counts; never perfect."""
    try:
        text = open(path, "r", encoding="utf-8", errors="replace").read()
    except OSError:
        return {"error": "unreadable"}
    # Try to find human-turn markers across formats
    markers = [
        r"^\s*(>\s*)?(human|user|me|you)\s*:",                 # "Human:" / "User:" / "> user:"
        r"^\s*#{1,4}\s*(human|user|prompt)\b",                 # "## User"
        r"^\s*\*\*(human|user|you)\*\*\s*:?",                  # "**User:**"
        r"^\s*\[(human|user)\]",                               # "[user]"
        r"^>\s+(?!\s*(assistant|claude|ai|gpt)\s*:)",          # Claude Code export: '> prompt'
    ]
    human_re = re.compile("|".join(f"(?:{m})" for m in markers), re.I | re.M)
    assistant_re = re.compile(r"^\s*(>\s*)?(assistant|claude|ai|gpt|cursor|copilot|model)\s*:|^\s*#{1,4}\s*(assistant|claude|ai|response)\b|^\s*\*\*(assistant|claude|ai)\*\*", re.I | re.M)

    # Split into blocks at any marker, keep role
    positions = []
    for m in human_re.finditer(text):
        positions.append((m.start(), "human", m.end()))
    for m in assistant_re.finditer(text):
        positions.append((m.start(), "assistant", m.end()))
    positions.sort()
    turns = []
    for idx, (start, role, body_start) in enumerate(positions):
        end = positions[idx + 1][0] if idx + 1 < len(positions) else len(text)
        body = text[body_start:end].strip()
        turns.append((role, body))
    human = [b for r, b in turns if r == "human"]
    if not human:
        return {"human_turns": 0, "note": "no human-turn markers recognised; count by hand"}
    short = [b for b in human if SHORT_APPROVAL.match(b) or len(b.split()) <= 3]
    direction = [b for b in human if DIRECTION_WORDS.search(b) and len(b.split()) > 3]
    first = human[0]
    return {
        "human_turns": len(human),
        "assistant_turns": sum(1 for r, _ in turns if r == "assistant"),
        "short_approval_turns": len(short),
        "short_approval_ratio": round(len(short) / len(human), 2),
        "direction_word_turns": len(direction),
        "direction_ratio": round(len(direction) / len(human), 2),
        "median_human_words": int(statistics.median(len(b.split()) for b in human)),
        "first_human_turn_words": len(first.split()),
        "first_human_turn_preview": first[:160].replace("\n", " "),
        "direction_turn_previews": [d[:140].replace("\n", " ") for d in direction[:8]],
    }


def main(argv):
    if len(argv) < 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    root = argv[1]
    as_json = "--json" in argv
    transcript = None
    mandated = []
    if "--transcript" in argv:
        transcript = argv[argv.index("--transcript") + 1]
    if "--mandated" in argv:
        mandated = [m.strip().lower() for m in argv[argv.index("--mandated") + 1].split(",") if m.strip()]

    files = []
    placeholders = []
    for p in walk_files(root):
        k = kind_of(p)
        try:
            size = os.path.getsize(p)
        except OSError:
            size = None
        entry = {"path": os.path.relpath(p, root if os.path.isdir(root) else os.path.dirname(root) or "."),
                 "bytes": size, "kind": k}
        if k == "text":
            entry["words"] = word_count(p)
            placeholders.extend(find_placeholders(p))
        files.append(entry)

    repo = git_summary(root) if os.path.isdir(root) else None

    mandated_report = {}
    lower_names = {os.path.basename(f["path"]).lower(): f["path"] for f in files}
    for m in mandated:
        mandated_report[m] = lower_names.get(m)

    result = {
        "root": root,
        "file_count": len(files),
        "files": files,
        "repository": repo,
        "mandated": mandated_report,
        "placeholders": placeholders,
        "transcript": transcript_stats(transcript) if transcript else None,
    }

    if as_json:
        print(json.dumps(result, indent=2, default=str))
        return 0

    def section(t):
        print("\n" + "=" * 78 + "\n" + t + "\n" + "=" * 78)

    section(f"FILES ({len(files)})")
    for f in files:
        w = f" · {f['words']} words" if f.get("words") is not None else ""
        print(f"  {f['path']}  ({f['bytes']} B, {f['kind']}{w})")

    section("REPOSITORY")
    if repo is None:
        print("  not a git repository")
    elif repo["commits"] == 0:
        print("  git repository with no commits")
    else:
        print(f"  commits: {repo['commits']}   span: {repo['span_hours']} h   first: {repo['first']}   last: {repo['last']}")
        print(f"  median message length: {repo['median_message_chars']} chars   weak messages (wip/fix/update): {repo['weak_messages']}   intent-bearing messages: {repo['intent_messages']}")
        if repo["future_dated_commits"]:
            print(f"  ⚠ future-dated commits: {len(repo['future_dated_commits'])} — {', '.join(repo['future_dated_commits'][:3])}")
        if repo["tracked_but_should_not_be"]:
            print(f"  ⚠ TRACKED IN HISTORY (reviewer will see): {', '.join(repo['tracked_but_should_not_be'][:6])}")
        for c in repo["log"][:40]:
            print(f"    {c['hash']}  {c['time']}  {c['subject']}")
        if repo["commits"] > 40:
            print(f"    … {repo['commits'] - 40} more")

    if mandated:
        section("MANDATED FILES")
        for m, found in mandated_report.items():
            print(f"  {m:30s} {'✓ ' + found if found else '✗ ABSENT'}")

    section(f"PLACEHOLDERS / LEFTOVERS ({len(placeholders)})")
    for h in placeholders[:60]:
        print(f"  {h['file']}:{h['line']}  [{h['kind']}]  {h['text']}")
    if len(placeholders) > 60:
        print(f"  … {len(placeholders) - 60} more")

    if transcript:
        section("TRANSCRIPT")
        t = result["transcript"]
        for k, v in t.items():
            if k == "direction_turn_previews":
                print("  direction-word turns (previews):")
                for d in v:
                    print(f"    - {d}")
            else:
                print(f"  {k}: {v}")
        print("  (ratios are heuristics; read the turns the previews point at)")

    print("\nThis is an inventory, not a judgment. Map each surface to the Lens's What-to-show table and read it.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
