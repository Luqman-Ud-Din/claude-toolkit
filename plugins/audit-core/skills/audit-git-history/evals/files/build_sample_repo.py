#!/usr/bin/env python3
"""Build a throwaway git repository with a scripted, dated history for audit-git-history
evals and parity checks. A skill must never ship a .git folder, so the repo is built on demand.

Usage:
    python build_sample_repo.py <target_dir> [--shallow-copy <dir>] [--force]

  <target_dir>     created fresh (must not exist unless --force, which deletes it first)
  --shallow-copy   also clone a --depth 2 copy there, to exercise shallow-clone detection

History on branch main (author and committer dates fixed with --date / GIT_COMMITTER_DATE):
  2023-02-10  PROJ-101 Initial import      src/OrderService.cs (line 6 TODO), src/legacy/Util.cs, README.md
  2023-06-14  Add deploy settings          config/.env (Stripe-shaped key), config/appsettings.Production.json
                                           (connection string with a password)
  2023-06-20  Remove committed secrets (SEC-7)
                                           deletes config/.env; replaces the password with a placeholder
  2024-01-15  Move Util to common, see #42 rename src/legacy/Util.cs -> src/common/Util.cs (+1 line)
  2025-11-03  AB#1234 Order totals rounding  edits src/OrderService.cs (TODO line untouched)
  2026-08-20  fix typo                     README.md (no ticket reference)
  2026-08-25  feature/export: PROJ-200 CSV export  (merged with --no-ff on 2026-08-27, "Merge branch
                                           'feature/export' (#57)")
  2026-08-26  feature/spike: Spike: GraphQL endpoint (never merged; branch kept)
  tag v1.0 on the 2024-01-15 commit; remote origin = https://github.com/example-org/sample-shop.git
The secrets are fake values assembled at runtime so this file does not trip secret scanners.
"""
import argparse
import os
import shutil
import stat
import subprocess
import sys

AUTHORS = {"imran": "imran@example.com", "sana": "sana@example.com", "bilal": "bilal@example.com"}


def git(repo, *args, date=None, author=None):
    env = dict(os.environ)
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"})
    if author:
        env.update({"GIT_AUTHOR_NAME": author, "GIT_AUTHOR_EMAIL": AUTHORS[author],
                    "GIT_COMMITTER_NAME": author, "GIT_COMMITTER_EMAIL": AUTHORS[author]})
    if date:
        env["GIT_COMMITTER_DATE"] = date
    r = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True, env=env)
    if r.returncode != 0:
        sys.exit("git %s failed: %s" % (" ".join(args), r.stderr.strip()))
    return r.stdout


def write(repo, rel, text):
    full = os.path.join(repo, *rel.split("/"))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def commit(repo, message, date, author):
    git(repo, "add", "-A", date=date, author=author)
    git(repo, "commit", "-q", "--no-verify", "-m", message, "--date", date, date=date, author=author)


def _rm_readonly(func, path, _):
    os.chmod(path, stat.S_IWRITE)
    func(path)


ORDER_V1 = """namespace Shop;

public class OrderService
{
    public decimal Total(decimal net, decimal tax)
    {   // TODO(imran): remove legacy tax path PROJ-99
        return net + tax;
    }
}
"""

ORDER_V2 = """namespace Shop;

public class OrderService
{
    public decimal Total(decimal net, decimal tax)
    {   // TODO(imran): remove legacy tax path PROJ-99
        return decimal.Round(net + tax, 2, MidpointRounding.AwayFromZero);
    }

    public decimal Discount(decimal total) => total > 100m ? total * 0.95m : total;
}
"""

UTIL = """namespace Shop.Legacy;

public static class Util
{
    public static string Clean(string s) => s.Trim();
}
"""


def build(target):
    stripe = "sk_" + "live_" + "9Qm2Zt7Lp4Xw8Rv3Nk6Hb1Jc"
    password = "Pr0d" + "Passw0rd" + "!2023"
    os.makedirs(target)
    git(target, "init", "-q", "-b", "main")
    git(target, "config", "core.autocrlf", "false")
    git(target, "remote", "add", "origin", "https://github.com/example-org/sample-shop.git")

    write(target, "src/OrderService.cs", ORDER_V1)
    write(target, "src/legacy/Util.cs", UTIL)
    write(target, "README.md", "# Sample shop\n\nRun with dotnet run.\n")
    commit(target, "PROJ-101 Initial import", "2023-02-10T10:00:00+00:00", "imran")

    write(target, "config/.env", "STRIPE_SECRET_KEY=%s\nLOG_LEVEL=info\n" % stripe)
    write(target, "config/appsettings.Production.json",
          '{\n  "ConnectionStrings": {\n    "Default": "Server=db;Database=shop;User Id=sa;Password=%s;"\n  }\n}\n' % password)
    commit(target, "Add deploy settings", "2023-06-14T11:20:00+00:00", "imran")

    git(target, "rm", "-q", "config/.env")
    write(target, "config/appsettings.Production.json",
          '{\n  "ConnectionStrings": {\n    "Default": "Server=db;Database=shop;User Id=sa;Password=${DB_PASSWORD};"\n  }\n}\n')
    commit(target, "Remove committed secrets (SEC-7)\n\nRotated the Stripe key; see incident notes.", "2023-06-20T09:00:00+00:00", "sana")

    os.makedirs(os.path.join(target, "src", "common"), exist_ok=True)
    git(target, "mv", "src/legacy/Util.cs", "src/common/Util.cs")
    write(target, "src/common/Util.cs", UTIL + "// moved from legacy\n")
    commit(target, "Move Util to common, see #42", "2024-01-15T14:00:00+00:00", "bilal")
    git(target, "tag", "v1.0", date="2024-01-15T14:05:00+00:00", author="bilal")

    write(target, "src/OrderService.cs", ORDER_V2)
    commit(target, "AB#1234 Order totals rounding", "2025-11-03T08:30:00+00:00", "sana")

    write(target, "README.md", "# Sample shop\n\nRun with `dotnet run`.\n")
    commit(target, "fix typo", "2026-08-20T16:00:00+00:00", "bilal")

    git(target, "checkout", "-q", "-b", "feature/export")
    write(target, "src/CsvExport.cs", "namespace Shop;\n\npublic class CsvExport { }\n")
    commit(target, "PROJ-200 CSV export", "2026-08-25T10:00:00+00:00", "sana")

    git(target, "checkout", "-q", "main")
    git(target, "checkout", "-q", "-b", "feature/spike")
    write(target, "src/GraphQl.cs", "namespace Shop;\n\npublic class GraphQlEndpoint { }\n")
    commit(target, "Spike: GraphQL endpoint", "2026-08-26T10:00:00+00:00", "bilal")

    git(target, "checkout", "-q", "main")
    d = "2026-08-27T09:00:00+00:00"
    git(target, "merge", "-q", "--no-ff", "--no-verify", "-m", "Merge branch 'feature/export' (#57)",
        "feature/export", date=d, author="imran")
    # --date is not accepted by merge; amend the author date so the merge is dated too.
    git(target, "commit", "-q", "--amend", "--no-edit", "--no-verify", "--date", d, date=d, author="imran")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("target")
    ap.add_argument("--shallow-copy")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    target = os.path.abspath(a.target)
    for path in [target] + ([os.path.abspath(a.shallow_copy)] if a.shallow_copy else []):
        if os.path.exists(path):
            if not a.force:
                sys.exit(path + " exists; pass --force to rebuild it")
            shutil.rmtree(path, onerror=_rm_readonly)
    build(target)
    if a.shallow_copy:
        url = "file:///" + target.replace("\\", "/").lstrip("/")
        r = subprocess.run(["git", "clone", "-q", "--depth", "2", url, os.path.abspath(a.shallow_copy)],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("shallow clone failed: " + r.stderr.strip())
    print(target)
    return 0


if __name__ == "__main__":
    sys.exit(main())
