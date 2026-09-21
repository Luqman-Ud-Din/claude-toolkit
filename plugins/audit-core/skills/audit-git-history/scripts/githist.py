#!/usr/bin/env python3
"""Factual git-history queries shared by every audit skill. It records facts only;
deciding whether a fact is a finding stays in the calling skill.

Usage (CLI):
    python githist.py log         <repo> [WINDOW] [--path P ...] [--all-refs] [--merges]
    python githist.py churn       <repo> [WINDOW] [--path P ...] [--range FILE:START-END ...] [--follow-renames]
    python githist.py blame       <repo> FILE [--lines START-END] [--group]
    python githist.py added-lines <repo> [--path P ...] [--max-commits 2000] [--head-only]
                                         [--since-days N] [--match REGEX] [--include-tree]
    python githist.py tickets     <repo> [WINDOW] [--path P ...] [--subject-only] [--no-merges] [--all-refs]
    python githist.py info        <repo> [--path PATHSPEC ...] [--contains REV ...] [--tags N]
    python githist.py <repo> [--history FILE] [--no-git] [--as-of YYYY-MM-DD]      (legacy summary)

  WINDOW   --since-days N  --last-commits N  (both apply when both are given; neither = all history)
  source   --history FILE  synthetic history JSON instead of git (format below)
           --no-git        read no history (mode "none")
  --as-of  YYYY-MM-DD reference date for windows and ages (default: synthetic head_date, else now)
  --out    write the JSON envelope to FILE and print the path; otherwise JSON goes to stdout

Importable (consumer scripts):
    import githist
    hist = githist.History(root, history_file=None, no_git=False)
    hist.commits(...), hist.churn(...), hist.range_churn(...), hist.hunks_for_file(...), hist.blame(...),
    hist.line_info(...), hist.last_change(...), hist.added_lines(...), hist.tree_lines(...),
    hist.tickets(...), hist.path_history(...), hist.refs_containing(...), hist.info(), hist.not_checked()
    githist.ticket_refs(text), githist.add_history_args(ap), githist.resolve_as_of(hist, arg)
Signatures and return shapes: references/githist-contract.md.

Modes:
  git        git on PATH and <repo> inside a work tree. Read-only commands only (log, show,
             blame, rev-parse, rev-list, ls-tree, for-each-ref, merge-base, tag, config --get).
  synthetic  --history FILE. Shape (only commits[].hash, commits[].date, files[].path required):
             {"head_date": "2026-09-01T10:00:00Z",
              "repo": {"branch": "main", "remote": "https://...", "tags": ["v1"], "shallow": false},
              "commits": [{"hash": "c10", "date": "...", "author": "dev", "message": "PROJ-1 subject",
                           "parents": ["c09"], "refs": ["refs/heads/main"],
                           "files": [{"path": "src/a.cs", "added": 40, "deleted": 3,
                                      "status": "A|M|D|R", "old_path": "src/old.cs",
                                      "functions": ["ImportOrders"], "hunks": [[120, 160]],
                                      "added_lines": [{"line": 12, "text": "..."}]}]}],
              "blame": {"src/a.cs": [{"lines": "1-400", "date": "...", "author": "dev", "commit": "c3"}]}}
             Blame picks the smallest range containing the line; a file with no blame entry
             falls back to the newest commit touching it, marked "approx": true.
  none       --no-git, git missing, or not a work tree: queries return empty results and
             not_checked() says why. A shallow clone is mode git with shallow=true; callers
             must report history-dependent answers as not checked (truncated).
Paths are repo-relative with forward slashes (relative to <repo> when it is a subfolder).
Read-only: nothing in the audited repository is modified.
"""
import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

def _audit_core_skills_dir():
    """Resolve the explicit core installation, or the original sibling layout."""
    env = os.environ.get("AUDIT_CORE_ROOT")
    if env:
        skills = os.path.join(env, "skills")
        if os.path.isdir(os.path.join(skills, "audit-code-scan")):
            return skills
        sys.exit("AUDIT_CORE_ROOT does not contain audit-core skills: " + env)
    sibling = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if os.path.isdir(os.path.join(sibling, "audit-code-scan")):
        return sibling
    sys.exit("audit-core is unavailable. Enable audit-core and restart Claude Code, "
             "or set AUDIT_CORE_ROOT to its plugin directory when running manually.")

_SKILLS = _audit_core_skills_dir()
_WALK = os.path.join(_SKILLS, "audit-code-scan", "scripts", "repo_walk.py")
try:
    import importlib.util as _ilu
    _walk_spec = _ilu.spec_from_file_location("audit_code_scan_repo_walk", _WALK)
    repo_walk = _ilu.module_from_spec(_walk_spec)
    _walk_spec.loader.exec_module(repo_walk)
except (FileNotFoundError, AttributeError, ImportError):
    sys.exit("audit-code-scan must be reachable from this skill (audit-core plugin or sibling layout; expected " + _WALK + ")")

CONTRACT_VERSION = "1.0"
TOOL = "audit-git-history"
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)
WORKING_TREE = "(working tree)"
SHALLOW_REASON = ("git work tree - SHALLOW clone: churn counts and blame ages are truncated; "
                  "run `git fetch --unshallow` in a copy or use --history")

# Ticket reference rules, applied in this order; the first rule to claim a span wins.
TICKET_RULES = [
    ("azure", re.compile(r"\bAB#(\d+)\b")),
    ("jira", re.compile(r"\b([A-Z][A-Z0-9]{1,9}-\d{1,6})\b")),
    ("github", re.compile(r"(?<![\w#])#(\d+)\b")),
    ("closing-keyword", re.compile(r"(?i)\b(?:fixes|closes|resolves)\s+(\d+)\b")),
]
# Upper-case tokens shaped like JIRA keys that name standards or encodings, not tickets.
NOT_TICKET_PREFIXES = frozenset({"UTF", "SHA", "ISO", "AES", "RSA", "HTTP", "TLS", "SSL", "RFC", "CVE", "CWE",
                                 "GHSA", "IPV", "ECMA", "ES", "WCAG", "ASVS", "OWASP", "COVID", "MD", "PEP"})
URL_RE = re.compile(r"https?://\S+")
HUNK_RE = re.compile(r"^@@+ (?:-\d+(?:,\d+)? )+\+(\d+)(?:,(\d+))? @@+")
_LOG_FMT = "%x1e%H%x1f%aI%x1f%an%x1f%ae%x1f%P%x1f%B%x1d"
_ZERO = "0" * 40


# --------------------------------------------------------------------------- helpers

def parse_date(s):
    if s is None:
        return None
    if isinstance(s, datetime):
        return s if s.tzinfo else s.replace(tzinfo=timezone.utc)
    if isinstance(s, (int, float)):
        return datetime.fromtimestamp(s, tz=timezone.utc)
    s = str(s).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        try:
            d = datetime.strptime(s[:10], "%Y-%m-%d")
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d


def iso(d):
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


def jsonable(obj):
    """Deep copy with datetimes as ISO-8601 UTC strings, tuples and sets as lists, '_'-prefixed keys dropped."""
    if isinstance(obj, datetime):
        return iso(obj)
    if isinstance(obj, dict):
        return {k: jsonable(v) for k, v in obj.items() if not (isinstance(k, str) and k.startswith("_"))}
    if isinstance(obj, (list, tuple)):
        return [jsonable(v) for v in obj]
    if isinstance(obj, (set, frozenset)):
        return sorted(jsonable(v) for v in obj)
    return obj


def _git(root, args, timeout=300):
    try:
        return subprocess.run(["git", "-c", "core.quotepath=off", "-C", root] + args, capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None


def _git_stream(root, args):
    """Yield decoded output lines of a long git command without holding the whole output in memory."""
    try:
        proc = subprocess.Popen(["git", "-c", "core.quotepath=off", "-C", root] + args,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return
    try:
        for raw in proc.stdout:
            yield raw.decode("utf-8", "replace").rstrip("\n").rstrip("\r")
    finally:
        proc.stdout.close()
        proc.wait()


def _unquote(p):
    """Undo git's C-style quoting of unusual paths ("a\\tb.cs")."""
    if len(p) < 2 or p[0] != '"' or p[-1] != '"':
        return p
    raw, out, i = p[1:-1], bytearray(), 0
    esc = {"n": 10, "t": 9, '"': 34, "\\": 92, "a": 7, "b": 8, "f": 12, "r": 13, "v": 11}
    while i < len(raw):
        ch = raw[i]
        if ch == "\\" and i + 1 < len(raw):
            nxt = raw[i + 1]
            if nxt in esc:
                out.append(esc[nxt])
                i += 2
                continue
            if re.match(r"[0-7]{3}", raw[i + 1:i + 4]):
                out.append(int(raw[i + 1:i + 4], 8))
                i += 4
                continue
        out.extend(ch.encode("utf-8"))
        i += 1
    return out.decode("utf-8", "replace")


def _resolve_rename(path):
    # numstat rename forms: "src/{old => new}/x.cs" or "old.cs => new.cs"
    m = re.match(r"^(.*)\{(.*) => (.*)\}(.*)$", path)
    if m:
        return (m.group(1) + m.group(3) + m.group(4)).replace("//", "/")
    if " => " in path:
        return path.split(" => ", 1)[1]
    return path


def _old_of_rename(path):
    m = re.match(r"^(.*)\{(.*) => (.*)\}(.*)$", path)
    if m:
        return (m.group(1) + m.group(2) + m.group(4)).replace("//", "/")
    if " => " in path:
        return path.split(" => ", 1)[0]
    return None


def path_matches(path, specs):
    """Synthetic-mode pathspec test: exact path, directory prefix, or glob (":(glob)" prefix allowed)."""
    if not specs:
        return True
    path = path.replace("\\", "/")
    for spec in specs:
        s = spec.replace("\\", "/")
        if s.startswith(":(glob)"):
            s = s[7:]
        s = s[2:] if s.startswith("./") else s
        if s in ("", "."):
            return True
        if path == s or path.startswith(s.rstrip("/") + "/") or fnmatch.fnmatchcase(path, s):
            return True
        if s.startswith("**/") and fnmatch.fnmatchcase(path, s[3:]):
            return True
    return False


def remote_provider(url):
    """github | gitlab | azure | bitbucket | other | none, from a remote URL."""
    if not url:
        return "none"
    low = url.lower()
    if "github.com" in low:
        return "github"
    if "gitlab" in low:
        return "gitlab"
    if "dev.azure.com" in low or "visualstudio.com" in low:
        return "azure"
    if "bitbucket" in low:
        return "bitbucket"
    return "other"


def ticket_refs(text, include_urls=False):
    """[{kind, id, match, start}] ticket references in text, in order, de-duplicated by id."""
    if not text:
        return []
    found, taken = [], []
    for kind, rx in TICKET_RULES:
        for m in rx.finditer(text):
            if any(m.start() < e and s < m.end() for s, e in taken):
                continue
            if kind == "jira" and m.group(1).split("-")[0] in NOT_TICKET_PREFIXES:
                continue
            ident = {"azure": "AB#" + m.group(1), "jira": m.group(1)}.get(kind, "#" + m.group(1))
            taken.append((m.start(), m.end()))
            found.append({"kind": kind, "id": ident, "match": m.group(0), "start": m.start()})
    if include_urls:
        for m in URL_RE.finditer(text):
            if not any(m.start() < e and s < m.end() for s, e in taken):
                found.append({"kind": "url", "id": m.group(0), "match": m.group(0), "start": m.start()})
    found.sort(key=lambda r: r["start"])
    seen, out = set(), []
    for r in found:
        if r["id"] not in seen:
            seen.add(r["id"])
            out.append(r)
    return out


def is_git_repo(root):
    r = _git(os.path.abspath(root), ["rev-parse", "--is-inside-work-tree"])
    return bool(r is not None and r.returncode == 0 and r.stdout.strip() == "true")


# --------------------------------------------------------------------------- History

class History:
    """Uniform access to commits, hunks, blame, added lines and refs. mode is 'git', 'synthetic' or 'none'."""

    def __init__(self, root, history_file=None, no_git=False):
        self.root = os.path.abspath(root)
        self.mode = "none"
        self.reason = ""
        self.data = None
        self.prefix = ""
        self.shallow = False
        self.git_available = shutil.which("git") is not None
        self._blame_cache = {}
        if history_file:
            with open(history_file, "r", encoding="utf-8") as fh:
                self.data = json.load(fh)
            self.mode = "synthetic"
            self.reason = "synthetic history from " + os.path.basename(history_file)
            for c in self.data.get("commits", []):
                c["_date"] = parse_date(c.get("date"))
            self.data.setdefault("commits", []).sort(key=lambda c: c["_date"] or EPOCH, reverse=True)
            self.shallow = bool((self.data.get("repo") or {}).get("shallow"))
        elif no_git:
            self.reason = "--no-git given"
        else:
            r = _git(self.root, ["rev-parse", "--is-inside-work-tree"])
            if r is None:
                self.reason = "git not found on PATH"
            elif r.returncode != 0 or r.stdout.strip() != "true":
                self.reason = "not a git work tree (pass --history FILE or --no-git)"
            else:
                self.mode = "git"
                p = _git(self.root, ["rev-parse", "--show-prefix"])
                self.prefix = p.stdout.strip() if p and p.returncode == 0 else ""
                self.reason = "git work tree"
                s = _git(self.root, ["rev-parse", "--is-shallow-repository"])
                if s is not None and s.stdout.strip() == "true":
                    self.shallow = True
                    self.reason = SHALLOW_REASON

    # ----------------------------------------------------------------- basics
    def default_as_of(self):
        if self.mode == "synthetic":
            hd = parse_date(self.data.get("head_date"))
            if hd:
                return hd
            if self.data.get("commits"):
                return self.data["commits"][0]["_date"]
        return datetime.now(timezone.utc)

    def not_checked(self):
        """[{item, reason}] the caller must list under Not checked."""
        out = []
        if self.mode == "none":
            out.append({"item": "git history", "reason": self.reason})
        if self.shallow:
            out.append({"item": "full git history", "reason": SHALLOW_REASON if self.mode == "git"
                        else "synthetic history is marked shallow"})
        return out

    def _rel(self, path):
        path = path.replace("\\", "/")
        if self.prefix and path.startswith(self.prefix):
            return path[len(self.prefix):]
        return path

    def _pathspec(self, paths):
        """Pathspec arguments. At the repo top with no filter none are passed, because any pathspec
        (even ".") turns on history simplification, which hides merge commits."""
        if paths:
            return ["--"] + list(paths)
        return ["--", "."] if self.prefix else []

    def _window_args(self, since_days, last_n, as_of):
        as_of = as_of or self.default_as_of()
        args = []
        if since_days:
            args.append("--since=" + (as_of - timedelta(days=since_days)).strftime("%Y-%m-%d"))
        args.append("--until=" + (as_of + timedelta(days=1)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00"))
        if last_n:
            args.append("-n%d" % last_n)
        return args

    def _synthetic_head_ref(self):
        b = (self.data.get("repo") or {}).get("branch")
        return "refs/heads/" + b if b else None

    def _synthetic(self, since_days=None, last_n=None, as_of=None, paths=None, all_refs=False, merges=False):
        """[(raw_commit, [raw_file, ...])] newest first after window, ref, merge and path filters."""
        as_of = as_of or self.default_as_of()
        cutoff = as_of - timedelta(days=since_days) if since_days else None
        head_ref = self._synthetic_head_ref()
        out = []
        for c in self.data.get("commits", []):
            d = c["_date"]
            if d and d > as_of + timedelta(days=1):
                continue
            if cutoff and d and d < cutoff:
                continue
            if not merges and len(c.get("parents") or []) > 1:
                continue
            if not all_refs and head_ref and c.get("refs") and head_ref not in c["refs"]:
                continue
            files = c.get("files", [])
            if paths:
                files = [f for f in files if path_matches(f["path"], paths)
                         or (f.get("old_path") and path_matches(f["old_path"], paths))]
                if not files:
                    continue
            out.append((c, files))
        return out[:last_n] if last_n else out

    # ----------------------------------------------------------------- commits
    def commits(self, since_days=None, last_n=None, as_of=None, paths=None, all_refs=False, merges=False,
                with_files=True):
        """Newest first: [{hash, hash_full, date, author, email, parents, subject, message,
        files:[{path, old_path, status, added, deleted, binary, functions, hunks}]}]."""
        out = []
        if self.mode == "synthetic":
            for c, files in self._synthetic(since_days, last_n, as_of, paths, all_refs, merges):
                msg = c.get("message", "") or ""
                out.append({"hash": c.get("hash"), "hash_full": c.get("hash"), "date": c["_date"],
                            "author": c.get("author", ""), "email": c.get("email", ""),
                            "parents": list(c.get("parents") or []), "subject": msg.split("\n", 1)[0],
                            "message": msg,
                            "files": [{"path": f["path"].replace("\\", "/"),
                                       "old_path": (f.get("old_path") or "").replace("\\", "/") or None,
                                       "status": f.get("status"), "added": f.get("added", 0),
                                       "deleted": f.get("deleted", 0), "binary": bool(f.get("binary")),
                                       "functions": f.get("functions"), "hunks": f.get("hunks")}
                                      for f in files] if with_files else []})
            return out
        if self.mode != "git":
            return out
        args = ["log", "--format=" + _LOG_FMT]
        if with_files:
            args += ["-M", "--raw", "--numstat"]
        if not merges:
            args.append("--no-merges")
        if all_refs:
            args.append("--all")
        args += self._window_args(since_days, last_n, as_of)
        args += self._pathspec(paths)
        r = _git(self.root, args, timeout=900)
        if r is None or r.returncode != 0:
            self.reason = "git log failed: " + ((r.stderr or "").strip()[:200] if r else "no process")
            return out
        for chunk in r.stdout.split("\x1e")[1:]:
            header, _, rest = chunk.partition("\x1d")
            h, d, an, ae, parents, body = (header.split("\x1f") + [""] * 6)[:6]
            body = body.strip("\n")
            cur = {"hash": h[:10], "hash_full": h, "date": parse_date(d), "author": an, "email": ae,
                   "parents": [p[:10] for p in parents.split()], "subject": body.split("\n", 1)[0],
                   "message": body, "files": []}
            out.append(cur)
            raws, nums = [], []
            for line in rest.splitlines():
                if line.startswith(":"):
                    raws.append(line)
                else:
                    parts = line.split("\t")
                    if len(parts) == 3:
                        nums.append(parts)
            paired = len(raws) == len(nums)
            for i, (add, dele, npath) in enumerate(nums):
                status, old, new = None, _old_of_rename(npath), _resolve_rename(npath)
                if paired:
                    meta, _, paths_part = raws[i].partition("\t")
                    code = meta.split()[-1] if meta.split() else ""
                    pp = [_unquote(x) for x in paths_part.split("\t")]
                    status = code[:1] or None
                    if status in ("R", "C") and len(pp) == 2:
                        old, new = pp
                    elif pp:
                        new, old = pp[-1], None
                else:
                    new = _unquote(new)
                cur["files"].append({"path": self._rel(new), "old_path": self._rel(old) if old else None,
                                     "status": status,
                                     "added": int(add) if add.isdigit() else 0,
                                     "deleted": int(dele) if dele.isdigit() else 0,
                                     "binary": add == "-" and dele == "-",
                                     "functions": None, "hunks": None})
        return out

    # ----------------------------------------------------------------- churn
    def churn(self, since_days=None, last_n=None, as_of=None, paths=None, all_refs=False, follow_renames=False):
        """Per-file churn, sorted by commits desc then path:
        [{path, commits, added, deleted, authors, author_names, first_change, last_change, renamed_from}]."""
        stats, alias = {}, {}
        for c in self.commits(since_days, last_n, as_of, paths, all_refs):
            seen = set()
            for f in c["files"]:
                p = alias.get(f["path"], f["path"]) if follow_renames else f["path"]
                if follow_renames and f.get("status") == "R" and f.get("old_path"):
                    alias[f["old_path"]] = p
                if p in seen:
                    continue
                seen.add(p)
                s = stats.setdefault(p, {"path": p, "commits": 0, "added": 0, "deleted": 0, "authors": 0,
                                         "author_names": set(), "first_change": None, "last_change": None,
                                         "renamed_from": set()})
                s["commits"] += 1
                s["added"] += f.get("added") or 0
                s["deleted"] += f.get("deleted") or 0
                if f["path"] != p:
                    s["renamed_from"].add(f["path"])
                if c.get("author"):
                    s["author_names"].add(c["author"])
                d = c["date"]
                if d and (s["last_change"] is None or d > s["last_change"]):
                    s["last_change"] = d
                if d and (s["first_change"] is None or d < s["first_change"]):
                    s["first_change"] = d
        rows = sorted(stats.values(), key=lambda s: (-s["commits"], s["path"]))
        for s in rows:
            s["author_names"] = sorted(s["author_names"])
            s["authors"] = len(s["author_names"])
            s["renamed_from"] = sorted(s["renamed_from"])
        return rows

    def hunks_for_file(self, relpath, since_days=None, last_n=None, as_of=None):
        """{commit_hash: [(start, end), ...]} changed new-side line ranges for one file."""
        res = {}
        relpath = relpath.replace("\\", "/")
        if self.mode == "synthetic":
            for c in self.commits(since_days, last_n, as_of):
                for f in c["files"]:
                    if f["path"] == relpath and f.get("hunks"):
                        res[c["hash"]] = [tuple(h) for h in f["hunks"]]
            return res
        if self.mode != "git":
            return res
        args = ["log", "--no-merges", "-p", "-U0", "--no-color", "--no-ext-diff", "--format=__C__%H"]
        args += self._window_args(since_days, last_n, as_of)
        args += ["--", relpath]
        r = _git(self.root, args, timeout=300)
        if r is None or r.returncode != 0:
            return res
        cur = None
        for line in r.stdout.splitlines():
            if line.startswith("__C__"):
                cur = line[5:].strip()[:10]
                res[cur] = []
            elif line.startswith("@@") and cur:
                m = re.match(r"@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
                if m:
                    start = int(m.group(1))
                    n = int(m.group(2)) if m.group(2) is not None else 1
                    res[cur].append((start, start + max(n, 1) - 1))
        return res

    def range_churn(self, relpath, ranges, since_days=None, last_n=None, as_of=None):
        """[{start, end, commits, hashes}] commits whose changed lines overlap each (start, end) range."""
        hunks = self.hunks_for_file(relpath, since_days, last_n, as_of)
        out = []
        for start, end in ranges:
            hs = [h for h, rs in hunks.items() if any(a <= end and start <= b for a, b in rs)]
            out.append({"start": start, "end": end, "commits": len(hs), "hashes": hs})
        return out

    # ----------------------------------------------------------------- blame
    def _git_blame(self, relpath):
        if relpath in self._blame_cache:
            return self._blame_cache[relpath]
        res = {}
        args = ["blame", "--line-porcelain"]
        top = _git(self.root, ["rev-parse", "--show-toplevel"])
        ignore = os.path.join(top.stdout.strip(), ".git-blame-ignore-revs") if top is not None and top.returncode == 0 else ""
        if ignore and os.path.exists(ignore):
            args += ["--ignore-revs-file", ignore]  # skip bulk reformat commits so ages stay meaningful
        r = _git(self.root, args + ["--", relpath], timeout=300)
        if r is not None and r.returncode == 0:
            cur, final_line = {}, None
            for line in r.stdout.splitlines():
                m = re.match(r"^([0-9a-f]{40}) (\d+) (\d+)", line)
                if m:
                    cur = {"commit": m.group(1)[:10], "approx": False, "boundary": False,
                           "uncommitted": m.group(1) == _ZERO, "original_line": int(m.group(2))}
                    final_line = int(m.group(3))
                elif line.startswith("author "):
                    cur["author"] = line[7:]
                elif line.startswith("author-time "):
                    cur["date"] = datetime.fromtimestamp(int(line[12:]), tz=timezone.utc)
                elif line.startswith("summary "):
                    cur["summary"] = line[8:]
                elif line == "boundary":
                    cur["boundary"] = True
                elif line.startswith("filename "):
                    cur["original_path"] = _unquote(line[9:])
                elif line.startswith("\t") and final_line is not None:
                    res[final_line] = dict(cur)
        self._blame_cache[relpath] = res
        return res

    def line_info(self, relpath, line):
        """{date, author, commit, approx, ...} for one line, or None."""
        relpath = relpath.replace("\\", "/")
        if self.mode == "git":
            return self._git_blame(relpath).get(line)
        if self.mode != "synthetic":
            return None
        best = None
        for e in self.data.get("blame", {}).get(relpath, []):
            a, _, b = str(e.get("lines", "")).partition("-")
            try:
                lo, hi = int(a), int(b or a)
            except ValueError:
                continue
            if lo <= line <= hi and (best is None or (hi - lo) < best[0]):
                best = (hi - lo, e)
        if best:
            e = best[1]
            return {"date": parse_date(e.get("date")), "author": e.get("author", ""),
                    "commit": e.get("commit", ""), "approx": False}
        last = self.last_change(relpath)
        if last:
            return dict(last, approx=True)
        return None

    def _synthetic_blame_end(self, relpath):
        lines = repo_walk.read_lines(os.path.join(self.root, relpath))
        if lines:
            return len(lines)
        ups = []
        for e in self.data.get("blame", {}).get(relpath, []):
            a, _, b = str(e.get("lines", "")).partition("-")
            try:
                ups.append(int(b or a))
            except ValueError:
                continue
        return max(ups) if ups else 0

    def blame(self, relpath, start=None, end=None, as_of=None):
        """[{line, commit, author, date, age_days, approx, boundary, uncommitted, summary, original_path}],
        one entry per line in [start, end]; lines with no answer carry commit None."""
        relpath = relpath.replace("\\", "/")
        as_of = as_of or self.default_as_of()
        if self.mode == "none":
            return []
        table = None
        if self.mode == "git":
            table = self._git_blame(relpath)
            if not table:
                return []
            lo, hi = start or 1, end or max(table)
        else:
            lo, hi = start or 1, end if end is not None else self._synthetic_blame_end(relpath)
        out = []
        for n in range(lo, hi + 1):
            info = (table.get(n) if table is not None else self.line_info(relpath, n)) or {}
            d = info.get("date")
            out.append({"line": n, "commit": info.get("commit") or None, "author": info.get("author"),
                        "date": d, "age_days": (as_of - d).days if d else None,
                        "approx": bool(info.get("approx")), "boundary": bool(info.get("boundary")),
                        "uncommitted": bool(info.get("uncommitted")), "summary": info.get("summary"),
                        "original_path": info.get("original_path")})
        return out

    @staticmethod
    def group_blame(entries):
        """Collapse consecutive lines from the same commit: [{start, end, lines, commit, author, date, age_days, approx, boundary, summary}]."""
        out = []
        for e in entries:
            if out and out[-1]["commit"] == e["commit"] and out[-1]["approx"] == e["approx"] and out[-1]["end"] == e["line"] - 1:
                out[-1]["end"] = e["line"]
                out[-1]["lines"] += 1
                continue
            out.append({"start": e["line"], "end": e["line"], "lines": 1, "commit": e["commit"], "author": e["author"],
                        "date": e["date"], "age_days": e["age_days"], "approx": e["approx"],
                        "boundary": e["boundary"], "summary": e["summary"]})
        return out

    def last_change(self, relpath):
        """{date, author, commit} of the newest commit touching the path (file or directory prefix)."""
        relpath = relpath.replace("\\", "/")
        if self.mode == "synthetic":
            for c in self.data.get("commits", []):
                for f in c.get("files", []):
                    p = f["path"].replace("\\", "/")
                    if p == relpath or p.startswith(relpath.rstrip("/") + "/"):
                        return {"date": c["_date"], "author": c.get("author", ""), "commit": c.get("hash", "")}
            return None
        if self.mode == "git":
            r = _git(self.root, ["log", "-1", "--format=%H%x09%aI%x09%an", "--", relpath])
            if r is not None and r.returncode == 0 and r.stdout.strip():
                h, d, a = (r.stdout.strip().split("\t") + ["", ""])[:3]
                return {"date": parse_date(d), "author": a, "commit": h[:10]}
        return None

    # ----------------------------------------------------------------- added lines
    def added_lines(self, paths=None, all_refs=True, max_commits=2000, since_days=None, as_of=None,
                    match=None, stats=None):
        """Generator of {hash, hash_full, author, date, file, line, text, source: "history"} for every line a
        commit added (new-side line number). Merge commits contribute only lines new to every parent.
        match: optional compiled regex or pattern string tested against text. stats: optional dict that
        receives {"commits_scanned": n} (complete once the generator is exhausted)."""
        if isinstance(match, str):
            match = re.compile(match)
        stats = stats if stats is not None else {}
        stats["commits_scanned"] = 0
        if self.mode == "synthetic":
            for c, files in self._synthetic(since_days, max_commits, as_of, paths, all_refs, merges=True):
                stats["commits_scanned"] += 1
                for f in files:
                    for al in f.get("added_lines") or []:
                        ln, text = (al.get("line"), al.get("text", "")) if isinstance(al, dict) else (al[0], al[1])
                        if match is not None and not match.search(text):
                            continue
                        yield {"hash": c.get("hash"), "hash_full": c.get("hash"), "author": c.get("author", ""),
                               "date": c["_date"], "file": f["path"].replace("\\", "/"), "line": ln, "text": text,
                               "source": "history"}
            return
        if self.mode != "git":
            return
        args = ["log", "-p", "--cc", "-U0", "--no-color", "--no-ext-diff", "--no-textconv", "-M",
                "--src-prefix=a/", "--dst-prefix=b/", "--format=%x1e%H%x1f%an%x1f%aI%x1f%P"]
        if all_refs:
            args.append("--all")
        if max_commits:
            args.append("--max-count=%d" % max_commits)
        args += self._window_args(since_days, None, as_of)
        args += self._pathspec(paths)
        cur, cur_file, in_hunk, new_line, width = None, None, False, 0, 1
        for line in _git_stream(self.root, args):
            if line.startswith("\x1e"):
                h, an, ad, parents = (line[1:].split("\x1f") + [""] * 4)[:4]
                cur = {"hash": h[:10], "hash_full": h, "author": an, "date": parse_date(ad)}
                width = max(1, len(parents.split()))
                cur_file, in_hunk = None, False
                stats["commits_scanned"] += 1
                continue
            if cur is None:
                continue
            if line.startswith("diff --git ") or line.startswith("diff --cc ") or line.startswith("diff --combined "):
                in_hunk, cur_file = False, None
                if not line.startswith("diff --git "):
                    cur_file = self._rel(_unquote(line.split(" ", 2)[2]))
                continue
            if line.startswith("@@"):
                m = HUNK_RE.match(line)
                if m:
                    new_line, in_hunk = int(m.group(1)), True
                    continue
            if not in_hunk:
                if line.startswith("+++ "):
                    p = _unquote(line[4:])
                    cur_file = None if p == "/dev/null" else self._rel(p[2:] if p.startswith("b/") else p)
                continue
            prefix, body = line[:width], line[width:]
            if len(prefix) < width or any(ch not in "+- " for ch in prefix):
                continue  # "\ No newline at end of file"
            if "-" in prefix:
                continue
            if cur_file and all(ch == "+" for ch in prefix) and (match is None or match.search(body)):
                yield dict(cur, file=cur_file, line=new_line, text=body, source="history")
            new_line += 1

    def tree_lines(self, paths=None, match=None, **walk_kwargs):
        """Generator of {hash: "(working tree)", hash_full, author: "", date: None, file, line, text, source: "tree"}
        for current files, walked with audit-code-scan's repo_walk.iter_files(root, **walk_kwargs)."""
        if isinstance(match, str):
            match = re.compile(match)
        for full in repo_walk.iter_files(self.root, **walk_kwargs):
            rel = repo_walk.rel(self.root, full)
            if paths and not path_matches(rel, paths):
                continue
            for n, text in enumerate(repo_walk.read_lines(full), 1):
                text = text.rstrip("\n").rstrip("\r")
                if match is not None and not match.search(text):
                    continue
                yield {"hash": WORKING_TREE, "hash_full": WORKING_TREE, "author": "", "date": None,
                       "file": rel, "line": n, "text": text, "source": "tree"}

    # ----------------------------------------------------------------- tickets
    def tickets(self, since_days=None, last_n=None, as_of=None, paths=None, all_refs=False, merges=True,
                subject_only=False, include_urls=False):
        """{commits: [{hash, hash_full, date, author, parents, subject, refs: [{kind, id, match, in}]}],
        summary: {commits, with_ref, without_ref, by_kind}}"""
        rows, by_kind = [], {}
        for c in self.commits(since_days, last_n, as_of, paths, all_refs, merges, with_files=False):
            subject = c["subject"]
            body = c["message"].split("\n", 1)[1] if "\n" in c["message"] else ""
            refs = [dict(r, **{"in": "subject"}) for r in ticket_refs(subject, include_urls)]
            if not subject_only:
                ids = {r["id"] for r in refs}
                refs += [dict(r, **{"in": "body"}) for r in ticket_refs(body, include_urls) if r["id"] not in ids]
            for r in refs:
                r.pop("start", None)
                by_kind[r["kind"]] = by_kind.get(r["kind"], 0) + 1
            rows.append({"hash": c["hash"], "hash_full": c["hash_full"], "date": c["date"], "author": c["author"],
                         "parents": len(c["parents"]), "subject": subject, "refs": refs})
        with_ref = sum(1 for r in rows if r["refs"])
        return {"commits": rows, "summary": {"commits": len(rows), "with_ref": with_ref,
                                             "without_ref": len(rows) - with_ref, "by_kind": by_kind}}

    # ----------------------------------------------------------------- paths and refs
    def path_history(self, pathspec, all_refs=True):
        """Per matching path: [{path, ever_committed, state, tracked_at_head, exists_in_worktree, added_in,
        deleted_in, renamed_to, events: [{hash, hash_full, date, author, status, path, old_path, subject}]}].
        Empty list: nothing matching was ever committed. state: tracked | deleted | renamed | not-at-head."""
        events = {}
        if self.mode == "synthetic":
            tracked = set()
            for c in reversed(self.data.get("commits", [])):
                for f in c.get("files", []):
                    p = f["path"].replace("\\", "/")
                    old = (f.get("old_path") or "").replace("\\", "/") or None
                    status = f.get("status") or ("M" if p in tracked else "A")
                    if status == "D":
                        tracked.discard(p)
                    else:
                        tracked.add(p)
                    if status == "R" and old:
                        tracked.discard(old)
                    ev = {"hash": c.get("hash"), "hash_full": c.get("hash"), "date": c["_date"],
                          "author": c.get("author", ""), "status": status, "path": p, "old_path": old,
                          "subject": (c.get("message") or "").split("\n", 1)[0]}
                    if path_matches(p, [pathspec]):
                        events.setdefault(p, []).append(ev)
                    if old and path_matches(old, [pathspec]):
                        events.setdefault(old, []).append(ev)
            tracked_head = {p for p in tracked if path_matches(p, [pathspec])}
        elif self.mode == "git":
            args = ["log", "-M", "--raw", "--no-merges", "--format=%x1e%H%x1f%aI%x1f%an%x1f%s%x1d"]
            if all_refs:
                args.append("--all")
            r = _git(self.root, args + ["--", pathspec], timeout=900)
            if r is not None and r.returncode == 0:
                for chunk in r.stdout.split("\x1e")[1:]:
                    header, _, rest = chunk.partition("\x1d")
                    h, d, an, subj = (header.split("\x1f") + [""] * 4)[:4]
                    for line in rest.splitlines():
                        if not line.startswith(":"):
                            continue
                        meta, _, pp = line.partition("\t")
                        parts = [self._rel(_unquote(x)) for x in pp.split("\t")]
                        status = meta.split()[-1][:1]
                        old, new = (parts[0], parts[1]) if status in ("R", "C") and len(parts) == 2 else (None, parts[-1])
                        if status == "D":
                            target = self._rename_target(h, new)  # pathspec hides the new side of a rename
                            if target:
                                status, old, new = "R", new, target
                        ev = {"hash": h[:10], "hash_full": h, "date": parse_date(d), "author": an, "status": status,
                              "path": new, "old_path": old, "subject": subj}
                        if path_matches(new, [pathspec]) or not old:
                            events.setdefault(new, []).append(ev)
                        if old:
                            events.setdefault(old, []).append(ev)
            lt = _git(self.root, ["ls-tree", "-r", "--name-only", "HEAD", "--", pathspec])
            tracked_head = ({self._rel(_unquote(x)) for x in lt.stdout.splitlines() if x}
                            if lt is not None and lt.returncode == 0 else set())
        else:
            return []
        for p in tracked_head:
            events.setdefault(p, [])
        out = []
        for p in sorted(events):
            evs = sorted(events[p], key=lambda e: e["date"] or EPOCH, reverse=True)
            newest = evs[0] if evs else None
            at_head = p in tracked_head
            if at_head:
                state = "tracked"
            elif newest and newest["status"] == "D":
                state = "deleted"
            elif newest and newest["status"] == "R" and newest.get("old_path") == p:
                state = "renamed"
            else:
                state = "not-at-head"
            adds = [e for e in evs if (e["status"] in ("A", "R", "C") and e["path"] == p)]
            dels = [e for e in evs if e["status"] == "D"]
            ren = next((e["path"] for e in evs if e["status"] == "R" and e.get("old_path") == p), None)
            out.append({"path": p, "ever_committed": bool(evs) or at_head, "state": state, "tracked_at_head": at_head,
                        "exists_in_worktree": os.path.exists(os.path.join(self.root, p)),
                        "added_in": adds[-1]["hash"] if adds else None,
                        "deleted_in": dels[0]["hash"] if dels else None, "renamed_to": ren, "events": evs})
        return out

    def _rename_target(self, commit, old_path):
        r = _git(self.root, ["show", "-M", "--raw", "--format=", commit, "--", "."])
        if r is None or r.returncode != 0:
            return None
        for line in r.stdout.splitlines():
            meta, _, pp = line.partition("\t")
            parts = [self._rel(_unquote(x)) for x in pp.split("\t")]
            if meta.startswith(":") and meta.split()[-1][:1] == "R" and len(parts) == 2 and parts[0] == old_path:
                return parts[1]
        return None

    def refs_containing(self, rev):
        """{rev, found, hash, hash_full, branches, remote_branches, tags, other_refs, reachable_from_head}."""
        res = {"rev": rev, "found": False, "hash": None, "hash_full": None, "branches": [], "remote_branches": [],
               "tags": [], "other_refs": [], "reachable_from_head": None}
        if self.mode == "synthetic":
            head_ref = self._synthetic_head_ref()
            c = next((c for c in self.data.get("commits", []) if str(c.get("hash", "")).startswith(rev)), None)
            if not c:
                return res
            res.update(found=True, hash=c["hash"], hash_full=c["hash"])
            refs = list(c.get("refs") or ([head_ref] if head_ref else []))
            if head_ref:
                res["reachable_from_head"] = head_ref in refs
        elif self.mode == "git":
            v = _git(self.root, ["rev-parse", "--verify", "--quiet", rev + "^{commit}"])
            if v is None or v.returncode != 0 or not v.stdout.strip():
                return res
            full = v.stdout.strip()
            res.update(found=True, hash=full[:10], hash_full=full)
            fr = _git(self.root, ["for-each-ref", "--contains", full, "--format=%(refname)"])
            refs = fr.stdout.split() if fr is not None and fr.returncode == 0 else []
            mb = _git(self.root, ["merge-base", "--is-ancestor", full, "HEAD"])
            res["reachable_from_head"] = bool(mb is not None and mb.returncode == 0)
        else:
            return res
        for ref in refs:
            if ref.startswith("refs/heads/"):
                res["branches"].append(ref[11:])
            elif ref.startswith("refs/remotes/"):
                res["remote_branches"].append(ref[13:])
            elif ref.startswith("refs/tags/"):
                res["tags"].append(ref[10:])
            else:
                res["other_refs"].append(ref)
        return res

    def info(self, tags_limit=20):
        """{is_git, git_available, mode, reason, shallow, toplevel, prefix, head, branch, detached, remote,
        remotes, provider, tags, commit_count, first_commit_date, last_commit_date, not_checked}."""
        res = {"is_git": self.mode == "git", "git_available": self.git_available, "mode": self.mode,
               "reason": self.reason, "shallow": self.shallow, "toplevel": None, "prefix": self.prefix or "",
               "head": None, "branch": None, "detached": None, "remote": None, "remotes": {}, "provider": "none",
               "tags": [], "commit_count": 0, "first_commit_date": None, "last_commit_date": None}
        if self.mode == "synthetic":
            repo = self.data.get("repo") or {}
            cs = self.data.get("commits", [])
            res.update(head=cs[0].get("hash") if cs else None, branch=repo.get("branch"),
                       detached=False if repo.get("branch") else None, remote=repo.get("remote"),
                       remotes={"origin": repo["remote"]} if repo.get("remote") else {},
                       provider=remote_provider(repo.get("remote")), tags=list(repo.get("tags") or [])[:tags_limit],
                       commit_count=len(cs), first_commit_date=cs[-1]["_date"] if cs else None,
                       last_commit_date=cs[0]["_date"] if cs else None)
        elif self.mode == "git":
            def out(args):
                r = _git(self.root, args)
                return r.stdout.strip() if r is not None and r.returncode == 0 else None
            res["toplevel"] = (out(["rev-parse", "--show-toplevel"]) or "").replace("\\", "/") or None
            res["head"] = out(["rev-parse", "--verify", "--quiet", "HEAD"])
            if res["head"]:
                b = out(["rev-parse", "--abbrev-ref", "HEAD"])
                res["branch"], res["detached"] = b, b == "HEAD"
                cnt = out(["rev-list", "--count", "HEAD"])
                res["commit_count"] = int(cnt) if cnt and cnt.isdigit() else 0
                res["last_commit_date"] = parse_date(out(["log", "-1", "--format=%aI"]))
                roots = [parse_date(x) for x in (out(["log", "--max-parents=0", "--format=%aI", "HEAD"]) or "").split()]
                roots = [d for d in roots if d]
                res["first_commit_date"] = min(roots) if roots else None
            else:
                sym = out(["symbolic-ref", "--short", "HEAD"])
                res["branch"], res["detached"] = sym, (False if sym else None)
            for line in (out(["config", "--get-regexp", r"^remote\..*\.url$"]) or "").splitlines():
                key, _, url = line.partition(" ")
                res["remotes"][key[len("remote."):-len(".url")]] = url
            res["remote"] = res["remotes"].get("origin")
            res["provider"] = remote_provider(res["remote"])
            res["tags"] = (out(["tag", "--sort=-creatordate"]) or "").split()[:tags_limit]
        res["not_checked"] = self.not_checked()
        return res


# --------------------------------------------------------------------------- consumer helpers

def add_history_args(ap):
    ap.add_argument("--history", help="synthetic history JSON (format in audit-git-history/references/githist-contract.md); use when the repo has no .git")
    ap.add_argument("--no-git", action="store_true", help="read no history; churn is empty and ages are null")
    ap.add_argument("--as-of", help="reference date YYYY-MM-DD for ages and windows (default: history head_date, else today)")


def resolve_as_of(hist, as_of_arg):
    return parse_date(as_of_arg) if as_of_arg else hist.default_as_of()


# --------------------------------------------------------------------------- CLI

SUBCOMMANDS = ("log", "churn", "blame", "added-lines", "tickets", "info")


def _parse_range(text):
    a, _, b = text.partition("-")
    return int(a), int(b or a)


def _build_parser():
    ap = argparse.ArgumentParser(prog="githist.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="command", required=True)

    def common(p, window=True, paths=True):
        p.add_argument("root")
        add_history_args(p)
        p.add_argument("--out", help="write the JSON envelope here and print the path")
        if window:
            p.add_argument("--since-days", type=int)
            p.add_argument("--last-commits", type=int)
        if paths:
            p.add_argument("--path", action="append", dest="paths", help="pathspec filter (repeatable)")
        return p

    p = common(sub.add_parser("log", help="commits with per-file numstat and rename resolution"))
    p.add_argument("--all-refs", action="store_true", help="every branch and tag, not just HEAD")
    p.add_argument("--merges", action="store_true", help="include merge commits (listed without files)")
    p = common(sub.add_parser("churn", help="per-file and per-line-range churn"))
    p.add_argument("--all-refs", action="store_true")
    p.add_argument("--follow-renames", action="store_true", help="fold pre-rename history into the newest path")
    p.add_argument("--range", action="append", dest="ranges", help="FILE:START-END line range churn (repeatable)")
    p = common(sub.add_parser("blame", help="blame age per line or range"), window=False, paths=False)
    p.add_argument("file")
    p.add_argument("--lines", help="START-END (default: whole file)")
    p.add_argument("--group", action="store_true", help="collapse consecutive lines from the same commit")
    p = common(sub.add_parser("added-lines", help="lines added per commit, for history secret scanning"), window=False)
    p.add_argument("--max-commits", type=int, default=2000)
    p.add_argument("--since-days", type=int)
    p.add_argument("--head-only", action="store_true", help="only commits reachable from HEAD (default: all refs)")
    p.add_argument("--match", help="only lines matching this regex")
    p.add_argument("--include-tree", action="store_true", help="also emit current working-tree lines")
    p = common(sub.add_parser("tickets", help="commit messages with ticket references"))
    p.add_argument("--all-refs", action="store_true")
    p.add_argument("--no-merges", action="store_true")
    p.add_argument("--subject-only", action="store_true")
    p = common(sub.add_parser("info", help="git or not, shallow, head/branch/remote/tags, path and ref questions"),
               window=False, paths=False)
    p.add_argument("--path", action="append", dest="paths", help="was PATHSPEC ever committed or later deleted (repeatable)")
    p.add_argument("--contains", action="append", default=[], help="refs containing REV (repeatable)")
    p.add_argument("--tags", type=int, default=20, help="max tags listed")
    return ap


def run_command(a):
    """Execute a parsed CLI namespace and return the JSON-ready envelope."""
    hist = History(a.root, a.history, a.no_git)
    as_of = resolve_as_of(hist, a.as_of)
    query = {k: v for k, v in vars(a).items() if k not in ("root", "history", "no_git", "as_of", "out", "command")}
    cmd = a.command
    if cmd == "log":
        cs = hist.commits(a.since_days, a.last_commits, as_of, a.paths, a.all_refs, a.merges)
        result = {"count": len(cs), "commits": cs}
    elif cmd == "churn":
        n = len(hist.commits(a.since_days, a.last_commits, as_of, a.paths, a.all_refs, with_files=False))
        result = {"commits_in_window": n,
                  "files": hist.churn(a.since_days, a.last_commits, as_of, a.paths, a.all_refs, a.follow_renames),
                  "ranges": []}
        for spec in a.ranges or []:
            f, _, rng = spec.rpartition(":")
            s, e = _parse_range(rng)
            for row in hist.range_churn(f, [(s, e)], a.since_days, a.last_commits, as_of):
                result["ranges"].append(dict(row, file=f.replace("\\", "/")))
    elif cmd == "blame":
        s, e = _parse_range(a.lines) if a.lines else (None, None)
        entries = hist.blame(a.file, s, e, as_of)
        result = {"file": a.file.replace("\\", "/"), "lines": [] if a.group else entries,
                  "ranges": History.group_blame(entries) if a.group else []}
    elif cmd == "added-lines":
        stats = {}
        rows = list(hist.added_lines(a.paths, not a.head_only, a.max_commits, a.since_days, as_of, a.match, stats))
        if a.include_tree:
            rows += list(hist.tree_lines(a.paths, a.match))
        result = {"commits_scanned": stats.get("commits_scanned", 0), "count": len(rows),
                  "commits_with_lines": sorted({r["hash_full"] for r in rows if r["source"] == "history"}),
                  "lines": rows}
    elif cmd == "tickets":
        result = hist.tickets(a.since_days, a.last_commits, as_of, a.paths, a.all_refs, not a.no_merges, a.subject_only)
    else:
        result = hist.info(a.tags)
        result["paths"] = [{"pathspec": ps, "matches": hist.path_history(ps)} for ps in (a.paths or [])]
        result["contains"] = [hist.refs_containing(rev) for rev in a.contains]
    return {"tool": TOOL, "contract": CONTRACT_VERSION, "command": cmd, "root": hist.root,
            "history": {"mode": hist.mode, "reason": hist.reason, "shallow": hist.shallow},
            "as_of": iso(as_of), "query": query, "not_checked": hist.not_checked(), "result": jsonable(result)}


def _legacy(argv):
    ap = argparse.ArgumentParser(prog="githist.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("root")
    add_history_args(ap)
    a = ap.parse_args(argv)
    h = History(a.root, a.history, a.no_git)
    cs = h.commits(last_n=5, as_of=resolve_as_of(h, a.as_of))
    print(json.dumps({"mode": h.mode, "reason": h.reason, "as_of": iso(resolve_as_of(h, a.as_of)),
                      "latest_commits": [{"hash": c["hash"], "date": iso(c["date"]), "files": len(c["files"])}
                                         for c in cs]}, indent=2))
    return 0


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] not in SUBCOMMANDS and not argv[0].startswith("-"):
        return _legacy(argv)
    a = _build_parser().parse_args(argv)
    text = json.dumps(run_command(a), indent=2, ensure_ascii=False)
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)) or ".", exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(a.out)
    else:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
