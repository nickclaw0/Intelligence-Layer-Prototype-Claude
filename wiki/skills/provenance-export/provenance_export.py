#!/usr/bin/env python3
"""
provenance-export engine.

Given a wiki page or a generated-output spec, extract every cited source ID,
resolve each against the raw manifest, and emit a report a compliance reviewer
can verify: which claims cite which sources, the source files behind them, and
any citation that cannot be resolved.

Usage:
    python3 provenance_export.py <target.md|spec.json> [--manifest <path>] [--format json|md]

Citations recognised: `^[src:ID]` (wiki inline form) and `[src:ID]` (rendered in decks/docs).
A citation matches a manifest source by exact id, short_ref, or unique id prefix.
"""
import sys, os, json, re, argparse

# The manifest lives in Layer 0 (Google Drive), outside this repo, so the path is
# machine-specific. Supply it per-device with the RAW_MANIFEST env var or --manifest.
# No hardcoded default: a stale absolute path silently resolves nothing on a teammate's box.
DEFAULT_MANIFEST = os.environ.get("RAW_MANIFEST", "")

MANIFEST_HINT = (
    "set the RAW_MANIFEST env var or pass --manifest; the manifest lives in the "
    "Google Drive folder 'Intelligence Layer Prototype_Claude_v1' at raw/_manifest.json"
)

CITE_RE = re.compile(r"\^?\[src:([^\]]+)\]")


def extract_claims(text):
    """Return list of (claim_text, [ids]) and a flat set of ids."""
    claims = []
    ids = set()
    # wiki inline form: [claim]^[src:id]
    for m in re.finditer(r"\[([^\]]+)\]\^\[src:([^\]]+)\]", text):
        claim, idlist = m.group(1), [x.strip() for x in m.group(2).split(",")]
        claims.append((claim, idlist))
        ids.update(idlist)
    # any other bare [src:id] occurrences
    for m in CITE_RE.finditer(text):
        for x in m.group(1).split(","):
            ids.add(x.strip())
    return claims, ids


def load_manifest(path):
    if not os.path.exists(path):
        return None
    return json.load(open(path))


def resolve(manifest, sid):
    if not manifest:
        return None
    for s in manifest.get("sources", []):
        if sid == s.get("id") or sid == s.get("short_ref"):
            return s
        if s.get("id", "").startswith(sid) and len(sid) >= 6:
            return s
    return None


def build_report(target, manifest):
    text = open(target, encoding="utf-8").read()
    claims, ids = extract_claims(text)
    sources, unresolved = [], []
    for sid in sorted(ids):
        s = resolve(manifest, sid)
        if s:
            sources.append({
                "cited_id": sid,
                "resolved_id": s.get("id"),
                "original_filename": s.get("original_filename"),
                "current_path": s.get("current_path"),
                "source_type": s.get("source_type"),
                "classification": s.get("classification"),
                "content_hash": s.get("content_hash"),
            })
        else:
            unresolved.append(sid)
    max_class = "public"
    order = ["public", "internal", "client-confidential", "regulated"]
    for s in sources:
        c = s.get("classification") or "public"
        if order.index(c) > order.index(max_class):
            max_class = c
    return {
        "target": os.path.basename(target),
        "claims_with_citations": [{"claim": c, "ids": i} for c, i in claims],
        "sources": sources,
        "unresolved_citations": unresolved,
        "inherited_sensitivity": max_class,
        "verifiable": len(unresolved) == 0,
    }


def to_md(r):
    lines = [f"# Provenance export: {r['target']}", ""]
    lines.append(f"- Inherited sensitivity: **{r['inherited_sensitivity']}**")
    lines.append(f"- Verifiable (all citations resolve): **{r['verifiable']}**")
    if r["unresolved_citations"]:
        lines.append(f"- UNRESOLVED citations: {', '.join(r['unresolved_citations'])}")
    lines.append("\n## Sources")
    for s in r["sources"]:
        lines.append(f"- `{s['cited_id']}` -> {s['original_filename']} "
                     f"({s['source_type']}, {s['classification']}) :: {s['current_path']}")
    lines.append("\n## Claims")
    for c in r["claims_with_citations"]:
        lines.append(f"- {c['claim']}  [{', '.join(c['ids'])}]")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--manifest", default=DEFAULT_MANIFEST)
    ap.add_argument("--format", choices=["json", "md"], default="json")
    args = ap.parse_args()
    if not args.manifest:
        sys.stderr.write(f"warning: no manifest path given; {MANIFEST_HINT}. Citations will be unresolved.\n")
        manifest = None
    else:
        manifest = load_manifest(args.manifest)
        if manifest is None:
            sys.stderr.write(f"warning: manifest not found at {args.manifest}; {MANIFEST_HINT}. Citations will be unresolved.\n")
    report = build_report(args.target, manifest)
    print(json.dumps(report, indent=2) if args.format == "json" else to_md(report))


if __name__ == "__main__":
    main()
