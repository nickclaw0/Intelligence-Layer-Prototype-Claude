# Ingest pipeline (Phase 3)

The Layer 0 -> Layer 1 on-ramp. An n8n workflow watches the Google Drive
`Ingest/` folder, normalises each new raw file into the `raw/...` tree under the
naming convention, hashes it, dedupes against `raw/_manifest.json`, appends a
manifest entry, writes the manifest back to Drive, and triggers the daily lint
so the new source folds into the wiki.

## Files

- [`velorixa-ingest-pipeline.n8n.json`](velorixa-ingest-pipeline.n8n.json) — import-ready n8n workflow.
- [`build_ingest_workflow.py`](build_ingest_workflow.py) — node-free generator that produces the JSON. Edit logic here and regenerate; do not hand-edit the JSON.

## What the workflow does

```
Drive Ingest Trigger (Ingest/ folder, fileCreated)
  -> Download Ingested File
  -> Normalize And Hash        (sha256 -> id + short_ref, parse naming convention, build manifest entry)
  -> IF Supported And Named
       true  -> Read Manifest  + Move File Into Raw
                -> Update Manifest (dedupe by content hash)
                -> IF New Source
                     true  -> Write Manifest To Drive -> Trigger Daily Lint
                     false -> Duplicate Source Skipped
       false -> Build Review Record -> Log Review For Human
```

Files that do not match `YYYY-MM-DD_VLX_<type>_<slug>_vN.ext` or are an
unsupported type are surfaced for human review, never silently dropped.

## Manifest reconciliation (the Phase 3 job)

Until this pipeline runs, the manifest `id` is the file's sha256 content hash
and `id_type` is `content-hash`. The workflow captures the Drive file id in a
`drive_file_id` field on each entry. The planned reconciliation step flips
`id_type` to `drive-file-id` and keeps the content hash in `content_hash`, so a
rename never orphans a citation. The current workflow records `drive_file_id`
on ingest; flipping `id_type` is a follow-up once every live entry carries one.

## Setup (do this in n8n; needs the live instance)

This repo ships the template. Wiring it to the running n8n instance is a manual,
credentialed step:

1. **Instance + key.** The n8n public-API key is held outside this repo (never
   commit it). The key alone does not name the instance; you import against your
   own n8n instance URL.
2. **Import.** n8n -> Workflows -> Import from File -> `velorixa-ingest-pipeline.n8n.json`.
3. **Credentials.** Attach a Google Drive OAuth credential to the four Drive
   nodes. These are created interactively in n8n and cannot be set from this repo.
4. **Replace the `REPLACE_WITH_*` placeholders:**
   - `REPLACE_WITH_INGEST_FOLDER_ID` — Drive folder id of `Ingest/`.
   - `REPLACE_WITH_MANIFEST_FILE_ID` — Drive file id of `raw/_manifest.json`.
   - `REPLACE_WITH_RAW_FOLDER_ID` — Drive folder id of the `raw/` root.
   - `REPLACE_WITH_GITHUB_PAT` — a fine-grained PAT with `contents:write` on
     `nickclaw0/Intelligence-Layer-Prototype-Claude`, used only to fire the lint
     via `repository_dispatch` (`event_type: raw-ingested`).
5. **Test.** Drop one correctly named file into `Ingest/`, run the workflow
   manually once, confirm the file moves into `raw/...`, the manifest gains one
   entry, and a duplicate of the same file is skipped on a second run.
6. **Activate** only after a clean manual run.

## Why this is a template, not a live deployment

The pipeline mutates Layer 0 (moves raw files, rewrites the manifest) and
triggers a commit-producing lint. That is shared, hard-to-reverse state, and it
needs Drive + GitHub credentials that must be created interactively inside n8n.
The repo therefore carries a reviewed, import-ready template; bringing it live is
a deliberate, credentialed step taken in the n8n instance.
