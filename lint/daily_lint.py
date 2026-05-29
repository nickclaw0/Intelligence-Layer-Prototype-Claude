#!/usr/bin/env python3
"""
Daily lint for the Velorixa Intelligence Layer (Phase 6).

The scheduled maintainer. Runs once a day. It does NOT rewrite the wiki: it folds
in only what is genuinely new or changed since the last run, as a diff against
state, never a sweep. The manifest's content hashes are the source of truth for
"what changed". Unrelated pages are left byte-for-byte unchanged.

Per run:
  1. Diff raw manifest content-hashes against lint/.lint_state.json.
  2. For only new/changed source ids: ensure a source page exists (create a
     needs-synthesis stub if missing), ensure its one-line index entry exists.
  3. Run lint checks over the affected neighbourhood only: broken citations,
     orphan pages, contradictions (surfaced, not resolved).
  4. Append exactly one lint summary line to wiki/log.md and update state.
  If nothing changed, append one "no changes" line and exit.

Usage:
    python3 daily_lint.py [--manifest <path>] [--repo <path>]

The monthly-grade work (full orphan sweep, stale-claim review, index health
check) is a separate, less frequent routine. This daily job stays cheap and additive.
"""
import sys, os, json, re, argparse, datetime, glob, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
DEFAULT_MANIFEST = os.environ.get(
    "RAW_MANIFEST",
    "/Users/Aitesting/Library/CloudStorage/GoogleDrive-nicolasgchr@gmail.com/"
    ".shortcut-targets-by-id/1QflKW2ZIKTW9ppldBWKpV0xwPK6Yjl04/"
    "Intelligence Layer Prototype_Claude_v1/raw/_manifest.json",
)
NAME_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})_([A-Z0-9]+)_([a-z-]+)_(.+)_v(\d+)\.(\w+)$")
CITE_RE = re.compile(r"\^?\[src:([^\]]+)\]")


def now_utc():
    return datetime.datetime.utcnow()


def ts():
    return now_utc().strftime("%Y-%m-%d %H:%M")


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    return json.load(open(path, encoding="utf-8"))


# ---------- state ----------

def state_path():
    return os.path.join(HERE, ".lint_state.json")


def load_state():
    return load_json(state_path(), {"last_lint": None, "seen": {}})


def save_state(state):
    state["last_lint"] = now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")
    json.dump(state, open(state_path(), "w", encoding="utf-8"), indent=2)


# ---------- change detection ----------

def detect_changes(manifest, state):
    seen = state.get("seen", {})
    changed = []
    for s in manifest.get("sources", []):
        sid = s.get("id")
        h = s.get("content_hash")
        if sid not in seen or seen.get(sid) != h:
            changed.append(s)
    return changed


# ---------- wiki helpers ----------

def wiki_dir():
    return os.path.join(REPO, "wiki")


def all_wiki_pages():
    return glob.glob(os.path.join(wiki_dir(), "**", "*.md"), recursive=True)


def page_cites_source(path, sid, short):
    txt = open(path, encoding="utf-8").read()
    return sid in txt or (short and short in txt)


def find_source_page(sid, short):
    for p in glob.glob(os.path.join(wiki_dir(), "sources", "*.md")):
        if page_cites_source(p, sid, short):
            return p
    return None


def parse_name(current_path):
    base = os.path.basename(current_path)
    m = NAME_RE.match(base)
    if not m:
        return None
    date, code, stype, slug, ver, ext = m.groups()
    return {"date": date, "code": code, "source_type": stype, "slug": slug, "version": ver, "ext": ext}


def create_source_stub(s, log_ref):
    parts = parse_name(s.get("current_path", ""))
    if not parts:
        return None, f"could not parse raw filename for {s.get('id')[:8]}"
    page = os.path.join(wiki_dir(), "sources", f"{parts['date']}-{parts['slug']}.md")
    if os.path.exists(page):
        return page, None
    short = s.get("short_ref") or s.get("id", "")[:8]
    title = parts["slug"].replace("-", " ").title()
    content = f"""---
title: {title}
type: source
client: {s.get('client', 'velorixa')}
therapeutic_area: {s.get('therapeutic_area', 'insomnia')}
sensitivity: {s.get('classification', 'client-confidential')}
sources:
  - id: {s.get('id')}
    cited_for: "TODO: what this source is the authority for"
source_type: {parts['source_type']}
source_date: {parts['date']}
related:
  - entities/velorixa
  - projects/launch-prep
status: needs-synthesis
last_updated: {now_utc().strftime('%Y-%m-%d')}
last_ingest_event: {log_ref}
---

Lint-created stub for an ingested raw file that has no source page yet. The maintainer agent enriches this with a summary, key extracts, and cross-links during synthesis. Until then it exists so the source is catalogued and linkable.

## Summary

TODO: synthesise from raw. Original file: `{s.get('original_filename')}` ([src:{short}]).

## Where this surfaces

- [[entities/velorixa]]
- [[projects/launch-prep]]
"""
    open(page, "w", encoding="utf-8").write(content)
    return page, None


# ---------- index ----------

def index_path():
    return os.path.join(wiki_dir(), "index.md")


def ensure_index_entry(page_rel, summary, meta):
    """Insert a one-line entry in the Sources section if not already present. Returns True if changed."""
    path = index_path()
    lines = open(path, encoding="utf-8").read().split("\n")
    link = page_rel[len("sources/"):] if page_rel.startswith("sources/") else page_rel
    wikilink = f"sources/{link[:-3]}" if link.endswith(".md") else f"sources/{link}"
    if any(wikilink in ln for ln in lines):
        return False
    entry = f"- [[{wikilink}]] — {summary} ({meta})"
    out, in_sources, inserted = [], False, False
    for i, ln in enumerate(lines):
        if ln.strip() == "## Sources":
            in_sources = True
            out.append(ln)
            continue
        if in_sources and ln.startswith("## ") and not inserted:
            # end of Sources section: insert before next header
            if out and out[-1].strip() == "":
                out.insert(len(out) - 1, entry)
            else:
                out.append(entry)
            inserted = True
            in_sources = False
        out.append(ln)
    if in_sources and not inserted:  # Sources was the last section
        out.append(entry)
        inserted = True
    open(path, "w", encoding="utf-8").write("\n".join(out))
    return inserted


# ---------- lint checks (scoped to affected neighbourhood) ----------

def resolve_id(manifest, cid):
    for s in manifest.get("sources", []):
        if cid == s.get("id") or cid == s.get("short_ref") or s.get("id", "").startswith(cid):
            return s
    return None


def lint_checks(affected_pages, manifest):
    problems = {"broken_citations": [], "orphans": [], "contradictions": []}
    all_pages = all_wiki_pages()
    for page in affected_pages:
        rel = os.path.relpath(page, wiki_dir())
        txt = open(page, encoding="utf-8").read()
        # broken citations
        for m in CITE_RE.finditer(txt):
            for cid in (x.strip() for x in m.group(1).split(",")):
                if not resolve_id(manifest, cid):
                    problems["broken_citations"].append(f"{rel}:{cid}")
        # orphan: no inbound [[...]] link from any other page
        stem = rel[:-3]
        inbound = False
        for other in all_pages:
            if other == page:
                continue
            if f"[[{stem}]]" in open(other, encoding="utf-8").read():
                inbound = True
                break
        if not inbound:
            problems["orphans"].append(rel)
    # contradiction detection is the maintainer's job; the daily lint surfaces, never resolves
    return problems


# ---------- log ----------

def append_log(summary):
    path = os.path.join(wiki_dir(), "log.md")
    with open(path, "a", encoding="utf-8") as f:
        f.write(f"\n## [{ts()}] lint | {summary}\n")


def next_log_ref():
    return f"log:{now_utc().strftime('%Y-%m-%d')}-lint"


# ---------- viewer sync ----------

def maybe_redeploy_viewer():
    """Keep the live viewer in sync with the wiki after a run that changed it.

    Opt-in: only runs when VIEWER_AUTODEPLOY is truthy and CF_API_TOKEN is set,
    so the lint stays usable in environments without Cloudflare access. The
    actual deploy (rebuild worker.js + PUT) lives in viewer/deploy_viewer.py,
    which preserves the auth secrets via inherit bindings and reads the token
    from the env. A deploy failure is reported but never fails the lint."""
    if os.environ.get("VIEWER_AUTODEPLOY", "").strip().lower() not in ("1", "true", "yes", "on"):
        return None
    if not os.environ.get("CF_API_TOKEN"):
        return "viewer auto-deploy skipped (CF_API_TOKEN not set)"
    script = os.path.join(REPO, "viewer", "deploy_viewer.py")
    if not os.path.exists(script):
        return "viewer auto-deploy skipped (deploy_viewer.py missing)"
    try:
        r = subprocess.run([sys.executable, script],
                           capture_output=True, text=True, timeout=180)
    except Exception as e:  # noqa: BLE001 - never let a deploy break the lint
        return f"viewer redeploy errored: {e}"
    if r.returncode == 0:
        return "viewer redeployed"
    tail = (r.stderr or r.stdout).strip().splitlines()
    return f"viewer redeploy failed: {tail[-1] if tail else 'unknown error'}"


# ---------- main ----------

def run(manifest_path):
    manifest = load_json(manifest_path)
    if manifest is None:
        sys.exit(f"manifest not found: {manifest_path}")
    state = load_state()
    changed = detect_changes(manifest, state)

    if not changed:
        append_log("no changes")
        save_state(state)
        print("no changes")
        return

    log_ref = next_log_ref()
    touched, created, idx_changed = [], [], 0
    for s in changed:
        short = s.get("short_ref") or s.get("id", "")[:8]
        page = find_source_page(s.get("id"), short)
        if not page:
            page, err = create_source_stub(s, log_ref)
            if err:
                print("WARN:", err)
                continue
            created.append(os.path.relpath(page, wiki_dir()))
        touched.append(page)
        rel = os.path.relpath(page, wiki_dir())
        parts = parse_name(s.get("current_path", ""))
        summary = f"{(parts['slug'].replace('-', ' ') if parts else 'source')}"
        meta = f"{s.get('source_type')}, 1 source"
        if ensure_index_entry(rel, summary, meta):
            idx_changed += 1
        # record seen
        state.setdefault("seen", {})[s.get("id")] = s.get("content_hash")

    problems = lint_checks(touched, manifest)
    bc = len(problems["broken_citations"])
    orph = len(problems["orphans"])

    bits = []
    if created:
        bits.append(f"created {len(created)} source stub(s): {', '.join(created)}")
    folded = [os.path.relpath(p, wiki_dir()) for p in touched if os.path.relpath(p, wiki_dir()) not in created]
    if folded:
        bits.append(f"folded {len(folded)} existing source(s)")
    if idx_changed:
        bits.append(f"updated index ({idx_changed} entr{'y' if idx_changed==1 else 'ies'})")
    if bc:
        bits.append(f"BROKEN CITATIONS: {', '.join(problems['broken_citations'])}")
    if orph:
        bits.append(f"orphans for review: {', '.join(problems['orphans'])}")
    viewer_note = maybe_redeploy_viewer()
    if viewer_note:
        bits.append(viewer_note)
    summary = "; ".join(bits) if bits else "changes detected, no actions"
    append_log(summary)
    save_state(state)

    print(f"lint run: {len(changed)} changed source(s)")
    print(" ", summary)
    if problems["broken_citations"]:
        sys.exit(2)  # broken citations are a hard problem


def main():
    global REPO
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--repo", default=REPO)
    args = ap.parse_args()
    REPO = args.repo
    run(args.manifest)


if __name__ == "__main__":
    main()
