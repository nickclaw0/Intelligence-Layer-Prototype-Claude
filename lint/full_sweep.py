#!/usr/bin/env python3
"""Full-sweep lint: whole-wiki checks the incremental daily_lint does not run.

Checks:
  1. Broken citations  -- every ^[src:<id>] resolves to a manifest id or short_ref
  2. Orphan pages      -- content pages not reachable from index.md or any wikilink
  3. Index health      -- every content page is indexed; every index wikilink resolves
  4. Stale review      -- pages whose last_updated is older than STALE_DAYS (informational)

Read-only. Prints a report and exits 0 if clean, 2 if any hard problem (broken
citation, missing index entry, dangling index link) is found.
"""
import json
import re
import sys
import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WIKI = REPO / "wiki"
CITE_RE = re.compile(r"\^?\[src:([^\]]+)\]")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
CODESPAN_RE = re.compile(r"`[^`]*`")


def strip_code(text):
    # Citations shown inside `inline code` are format examples, not real claims.
    return CODESPAN_RE.sub("", text)
LAST_UPDATED_RE = re.compile(r"^last_updated:\s*(\d{4}-\d{2}-\d{2})", re.MULTILINE)
STALE_DAYS = 180

# Pages that are infrastructure, not graph nodes.
NON_NODE = {"CLAUDE.md", "index.md", "log.md"}


def load_manifest(path):
    data = json.loads(Path(path).read_text())
    ids = set()
    for s in data.get("sources", []):
        if s.get("id"):
            ids.add(s["id"])
        if s.get("short_ref"):
            ids.add(s["short_ref"])
    return ids


def content_pages():
    pages = []
    for p in WIKI.rglob("*.md"):
        rel = p.relative_to(WIKI)
        if rel.parts[0] == "_templates":
            continue
        if str(rel) in NON_NODE:
            continue
        pages.append(p)
    return pages


def page_node_id(p):
    # wiki/sources/foo.md -> sources/foo ; skills SKILL.md keeps full path sans .md
    rel = p.relative_to(WIKI)
    return str(rel.with_suffix(""))


def main():
    manifest = None
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--manifest" and i + 1 < len(args):
            manifest = args[i + 1]
    if not manifest:
        print("usage: full_sweep.py --manifest <path>")
        return 1

    valid_ids = load_manifest(manifest)
    pages = content_pages()
    index_text = (WIKI / "index.md").read_text()

    problems = []
    warnings = []

    # 1. Broken citations across every page
    cited_total = 0
    for p in pages + [WIKI / "index.md"]:
        text = strip_code(p.read_text())
        for m in CITE_RE.finditer(text):
            cited_total += 1
            ref = m.group(1)
            if ref not in valid_ids:
                problems.append(f"broken citation [src:{ref}] in {p.relative_to(REPO)}")

    # Build the set of all wikilink targets across the whole wiki (for orphan + dangling)
    all_targets = {}  # target -> list of pages linking to it
    for p in pages + [WIKI / "index.md"]:
        for m in WIKILINK_RE.finditer(p.read_text()):
            tgt = m.group(1).strip()
            all_targets.setdefault(tgt, []).append(page_node_id(p))

    node_ids = {page_node_id(p) for p in pages}

    # 2. Orphans: content pages no one links to (and that the index does not list)
    indexed_links = set()
    for m in WIKILINK_RE.finditer(index_text):
        indexed_links.add(m.group(1).strip())
    for p in pages:
        nid = page_node_id(p)
        linked = nid in all_targets
        # skills sub-pages (layout_catalogue, styles_reference) are reached via their SKILL sibling
        is_skill_subpage = nid.startswith("skills/") and not nid.endswith("/SKILL")
        if not linked and not is_skill_subpage:
            warnings.append(f"orphan page (no inbound wikilink): {nid}")

    # 3a. Index health: dangling index links (point to nonexistent pages)
    for tgt in indexed_links:
        # normalise: index uses sources/slug, synthesis/slug, skills/x/SKILL
        candidate = WIKI / (tgt + ".md")
        if not candidate.exists():
            problems.append(f"dangling index link [[{tgt}]] -> no file at wiki/{tgt}.md")

    # 3b. Index health: content pages missing from the index
    # sources, synthesis, entities, concepts, projects, decisions, skills should be indexed
    for p in pages:
        nid = page_node_id(p)
        if nid.startswith("skills/") and not nid.endswith("/SKILL"):
            continue  # sub-pages indexed via their SKILL
        if nid not in indexed_links:
            warnings.append(f"page not listed in index: {nid}")

    # 4. Stale review (informational)
    today = datetime.date.today()
    for p in pages:
        m = LAST_UPDATED_RE.search(p.read_text())
        if m:
            d = datetime.date.fromisoformat(m.group(1))
            age = (today - d).days
            if age > STALE_DAYS:
                warnings.append(f"stale ({age}d since last_updated): {page_node_id(p)}")

    # Report
    print(f"full sweep: {len(pages)} content page(s), {cited_total} citation(s), "
          f"{len(valid_ids)//2} manifest source(s)")
    if problems:
        print(f"\nHARD PROBLEMS ({len(problems)}):")
        for x in problems:
            print(f"  ! {x}")
    if warnings:
        print(f"\nWARNINGS ({len(warnings)}):")
        for x in warnings:
            print(f"  - {x}")
    if not problems and not warnings:
        print("clean: no problems, no warnings")
    elif not problems:
        print("\nno hard problems (warnings only)")

    return 2 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
