#!/usr/bin/env python3
"""
skill-creator engine (meta-skill).

Draft, lint, and propose new skills. Enforces the client-portability rule: a
skill built for one tenant is not reusable in another without explicit review
and reauthoring, so every skill is stamped with its client.

Usage:
    python3 skill_creator.py scaffold <skill-name> [--client velorixa] [--desc "..."]
    python3 skill_creator.py lint <skill-dir-name|all>
"""
import sys, os, argparse, glob

SKILLS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REQUIRED = ["name", "description", "triggers", "required_tools", "inputs", "outputs", "sensitivity", "client"]

TEMPLATE = """---
name: {name}
description: {desc}
triggers:
  - query_patterns: ["TODO"]
  - event: TODO
required_tools:
  - file_read
related_wiki:
  - projects/{{active}}
inputs:
  - TODO: string
outputs:
  - TODO
sensitivity: inherits_from_project
client: {client}
---

TODO: one-paragraph statement of what this skill does.

## How to build

1. Read the relevant wiki pages and gather content with source IDs.
2. TODO steps.
3. File a completion record back into the wiki and append a line to `log.md`.

## Rules

- Provenance is mandatory: every factual claim cites a source.
- Sensitivity inherits per `../../CLAUDE.md`.
- Authored for the {client} tenant. Not reusable in another tenant without review and reauthoring.
"""


def scaffold(name, client, desc):
    d = os.path.join(SKILLS_DIR, name)
    if os.path.exists(d):
        sys.exit(f"skill already exists: {name}")
    os.makedirs(d)
    open(os.path.join(d, "SKILL.md"), "w").write(
        TEMPLATE.format(name=name, client=client, desc=desc or "TODO describe the skill")
    )
    print(f"Scaffolded skills/{name}/SKILL.md (client={client}). Fill in the TODOs, then run lint and skill-test.")


def lint_one(name):
    path = os.path.join(SKILLS_DIR, name, "SKILL.md")
    if not os.path.exists(path):
        return [f"missing SKILL.md"]
    txt = open(path, encoding="utf-8").read()
    if not txt.startswith("---"):
        return ["no frontmatter block"]
    fm = txt.split("---", 2)[1]
    problems = [f"missing '{k}'" for k in REQUIRED if f"{k}:" not in fm]
    if "client:" in fm and "not reusable in another tenant" not in txt.lower():
        problems.append("body missing the client-portability statement")
    return problems


def lint(target):
    names = ([os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(SKILLS_DIR, "*", "SKILL.md"))]
             if target == "all" else [target])
    failed = 0
    for name in sorted(names):
        problems = lint_one(name)
        if problems:
            failed += 1
            print(f"FAIL  {name}")
            for p in problems:
                print(f"      - {p}")
        else:
            print(f"PASS  {name}")
    sys.exit(1 if failed else 0)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scaffold"); s.add_argument("name"); s.add_argument("--client", default="velorixa"); s.add_argument("--desc", default="")
    l = sub.add_parser("lint"); l.add_argument("target")
    args = ap.parse_args()
    if args.cmd == "scaffold":
        scaffold(args.name, args.client, args.desc)
    else:
        lint(args.target)


if __name__ == "__main__":
    main()
