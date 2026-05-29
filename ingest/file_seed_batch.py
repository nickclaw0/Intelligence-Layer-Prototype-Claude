#!/usr/bin/env python3
"""Bootstrap-file the Ingest/ seed batch into raw/ following the convention.

Loose by-type seed files (Internal PPTs, Meeting transcripts, Scientific
literature) are classified and routed into the raw hierarchy:

    raw/{client}/{ta}/{project}/{source-type}/
        {YYYY-MM-DD}_{client-code}_{source-type}_{slug}_v{n}.{ext}

For each file we compute the sha256 content id, write a `.meta.json` sidecar
(meta.schema.json), copy the file into raw (raw is immutable: copy, never move
or overwrite), and append a manifest entry. Idempotent: a file whose content
hash already appears in the manifest is skipped.

This is the human-confirmed bootstrap classification the raw/README.md ingest
routing (step 3) calls for; the Phase 3 n8n pipeline does the same thing
going forward.

Usage:
    python3 ingest/file_seed_batch.py --drive "<prototype root>" [--apply]
Without --apply it prints the plan and writes nothing.
"""
import argparse, hashlib, json, re, shutil, sys
from datetime import datetime, timezone
from pathlib import Path

CLIENT = "velorixa"
CLIENT_CODE = "VLX"
TA = "insomnia"
PROJECT = "launch-prep"
INGEST_DATE = "2026-05-29"
CLASSIFICATION = "client-confidential"  # start-strict per raw/README.md
RETENTION = "default-7y"

# by-type seed subfolder -> closed-vocabulary source-type
FOLDER_SOURCE_TYPE = {
    "Meeting transcripts": "transcript",
    "Internal PPTs": "strategy-doc",
    "Scientific literature": "research",
}

# Research PDFs whose publication date is not machine-extractable; we fall back
# to the ingest date and record that in the manifest note.
PDF_DATE_FALLBACK = INGEST_DATE


def kebab(text, max_chars=60):
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if len(s) <= max_chars:
        return s
    cut = s[:max_chars]
    if "-" in cut:
        cut = cut.rsplit("-", 1)[0]
    return cut.strip("-")


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def transcript_date(path):
    # Header line "Date: YYYY-MM-DD"
    with open(path, "r", errors="ignore") as f:
        head = f.read(2000)
    m = re.search(r"Date:\s*(\d{4}-\d{2}-\d{2})", head)
    return m.group(1) if m else None


def pptx_date(path):
    import zipfile
    try:
        with zipfile.ZipFile(path) as z:
            xml = z.read("docProps/core.xml").decode("utf-8", "ignore")
    except Exception:
        return None
    m = re.search(r"<dcterms:created[^>]*>(\d{4}-\d{2}-\d{2})", xml)
    return m.group(1) if m else None


def pdf_date(path):
    raw = open(path, "rb").read()
    m = re.search(rb"/CreationDate\s*\(D:(\d{4})(\d{2})(\d{2})", raw)
    if m:
        y, mo, d = (g.decode() for g in m.groups())
        return f"{y}-{mo}-{d}", True
    return PDF_DATE_FALLBACK, False


def slug_for(source_type, original_filename):
    stem = Path(original_filename).stem
    if source_type == "transcript":
        # Velorixa_Transcript_03_Proposal_Scope_and_Budget
        m = re.match(r"Velorixa_Transcript_\d+_(.+)$", stem)
        return kebab(m.group(1) if m else stem)
    if source_type == "strategy-doc":
        # Velorixa_01_Brand_Foundation
        m = re.match(r"Velorixa_\d+_(.+)$", stem)
        return kebab(m.group(1) if m else stem)
    if source_type == "research":
        # 12_PMID_41757443_PMC12962709_Title words...
        m = re.match(r"\d+_PMID_(\d+)_PMC(\d+)_(.+)$", stem)
        if m:
            pmid, _pmc, title = m.groups()
            return f"pmid{pmid}-{kebab(title, 48)}"
        return kebab(stem)
    return kebab(stem)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--drive", required=True, help="prototype root containing Ingest/ and raw/")
    ap.add_argument("--apply", action="store_true", help="write files; otherwise dry-run")
    args = ap.parse_args()

    root = Path(args.drive)
    ingest = root / "Ingest"
    raw = root / "raw"
    manifest_path = raw / "_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    existing_hashes = {s["content_hash"] for s in manifest["sources"]}
    existing_paths = {s["current_path"] for s in manifest["sources"]}

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    planned, skipped = [], []

    for folder, source_type in FOLDER_SOURCE_TYPE.items():
        src_dir = ingest / folder
        if not src_dir.is_dir():
            continue
        for f in sorted(src_dir.iterdir()):
            if f.name.startswith(".") or not f.is_file():
                continue
            content_hash = "sha256:" + sha256_of(f)
            if content_hash in existing_hashes:
                skipped.append((f.name, "duplicate content already in manifest"))
                continue

            ext = f.suffix.lstrip(".")
            note = "Phase 3 bootstrap: human-confirmed classification of seed batch."
            if source_type == "transcript":
                date = transcript_date(f)
            elif source_type == "strategy-doc":
                date = pptx_date(f) or INGEST_DATE
            else:  # research
                date, exact = pdf_date(f)
                if not exact:
                    note += " Publication date not machine-extractable from PDF; source_date set to ingest date."
            if not date:
                date = INGEST_DATE

            slug = slug_for(source_type, f.name)
            rel_dir = f"raw/{CLIENT}/{TA}/{PROJECT}/{source_type}"
            version = 1
            fname = f"{date}_{CLIENT_CODE}_{source_type}_{slug}_v{version}.{ext}"
            current_path = f"{rel_dir}/{fname}"
            # version bump guard if path collision with a different file
            while current_path in existing_paths or current_path in {p["current_path"] for p in planned}:
                version += 1
                fname = f"{date}_{CLIENT_CODE}_{source_type}_{slug}_v{version}.{ext}"
                current_path = f"{rel_dir}/{fname}"

            cid = content_hash.split(":", 1)[1]
            planned.append({
                "src": f,
                "current_path": current_path,
                "content_hash": content_hash,
                "id": cid,
                "short_ref": cid[:8],
                "original_filename": f.name,
                "source_type": source_type,
                "source_date": date,
                "size_bytes": f.stat().st_size,
                "note": note,
            })

    print(f"== plan: {len(planned)} to file, {len(skipped)} skipped ==")
    for p in planned:
        print(f"  [{p['source_type']:12}] {p['short_ref']}  {p['current_path'].split('/')[-1]}")
    for name, why in skipped:
        print(f"  SKIP {name}: {why}")

    if not args.apply:
        print("\n(dry run; pass --apply to write)")
        return

    # write files
    for p in planned:
        dest = root / p["current_path"]
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p["src"], dest)
        meta = {
            "id": p["id"],
            "id_type": "content-hash",
            "content_hash": p["content_hash"],
            "original_filename": p["original_filename"],
            "uploader": "unknown",
            "source_date": p["source_date"],
            "upload_date": INGEST_DATE,
            "ingest_date": INGEST_DATE,
            "client": CLIENT,
            "client_code": CLIENT_CODE,
            "therapeutic_area": TA,
            "project": PROJECT,
            "source_type": p["source_type"],
            "classification": CLASSIFICATION,
            "retention_policy": RETENTION,
            "compliance_tags": [],
            "schema": "_schemas/meta.schema.json",
        }
        (dest.parent / (dest.name + ".meta.json")).write_text(
            json.dumps(meta, indent=2) + "\n")
        manifest["sources"].append({
            "id": p["id"],
            "id_type": "content-hash",
            "short_ref": p["short_ref"],
            "current_path": p["current_path"],
            "content_hash": p["content_hash"],
            "original_filename": p["original_filename"],
            "client": CLIENT,
            "therapeutic_area": TA,
            "project": PROJECT,
            "source_type": p["source_type"],
            "classification": CLASSIFICATION,
            "size_bytes": p["size_bytes"],
            "ingest_history": [{
                "event": "bootstrap-ingest",
                "timestamp": now,
                "actor": "claude-maintainer",
                "from": f"Ingest/{p['src'].relative_to(ingest)}",
                "version": int(re.search(r'_v(\d+)\.', p['current_path']).group(1)),
                "note": p["note"],
            }],
        })

    manifest["last_updated"] = now
    manifest["generated_by"] = "phase-3-bootstrap-ingest"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"\napplied: filed {len(planned)} files; manifest now has {len(manifest['sources'])} sources")


if __name__ == "__main__":
    sys.exit(main())
