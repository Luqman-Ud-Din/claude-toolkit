#!/usr/bin/env python3
"""Load and filter shared-llm-payload-library's payloads.json.

Usage:
    python payloads.py                          # print all entries
    python payloads.py --category jailbreak_roleplay
    python payloads.py --list-categories
"""
import argparse
import json
import os

DEFAULT_PATH = os.path.join(os.path.dirname(__file__), "..", "references", "payloads.json")


def load(path=DEFAULT_PATH):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default=DEFAULT_PATH)
    ap.add_argument("--category")
    ap.add_argument("--list-categories", action="store_true")
    args = ap.parse_args()

    payloads = load(args.path)

    if args.list_categories:
        for cat in sorted({p["category"] for p in payloads}):
            print(cat)
        return

    if args.category:
        payloads = [p for p in payloads if p["category"] == args.category]

    print(json.dumps(payloads, indent=2))


if __name__ == "__main__":
    main()
