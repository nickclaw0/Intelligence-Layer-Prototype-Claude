---
name: provenance-export
description: Export every claim, source, and touched page for an output so a compliance reviewer can verify it
triggers:
  - query_patterns: ["provenance", "audit this", "compliance export", "where did this come from"]
  - event: output_generated
required_tools:
  - file_read
  - drive_read
inputs:
  - target: string         # a wiki page path or a generated-output spec
outputs:
  - provenance_report.json
sensitivity: inherits_from_target
client: velorixa
---

Export the full provenance of any wiki page or generated output: every cited claim, the raw source behind each citation, the inherited sensitivity, and any citation that fails to resolve. Build this from day one so every deck, document, or page can be verified against the source of truth.

## Engine

`provenance_export.py`. It reads the target, extracts citations in both the wiki inline form `[claim]^[src:id]` and the rendered form `[src:id]`, resolves each against `/raw/_manifest.json`, and emits a report.

```
python3 provenance_export.py <target.md|spec.json> --format md
python3 provenance_export.py <target.md|spec.json> --format json --manifest <path-to-_manifest.json>
```

The manifest path defaults to the Drive raw manifest and can be overridden with `--manifest` or the `RAW_MANIFEST` environment variable. In production the orchestration layer supplies it.

## Report contents

- Each claim and the source IDs it cites.
- Each source resolved to its original filename, current raw path, source-type, classification, and content hash.
- The inherited sensitivity (the highest classification among cited sources).
- Any unresolved citation, with `verifiable` set false if any exist.

## Rules

- A `verifiable: false` result blocks release. Every citation must resolve to a manifest entry before an output leaves the system.
- Regulated or client-confidential provenance follows the gating rules in `../../CLAUDE.md`.
- Authored for the velorixa tenant. Not reusable in another tenant without review and reauthoring.
