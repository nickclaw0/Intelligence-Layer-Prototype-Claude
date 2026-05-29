---
title: TITLE
type: source
client: velorixa
therapeutic_area: insomnia
sensitivity: client-confidential   # inherits from the cited raw file's classification
sources:
  - id: RAW_DOC_ID                 # the raw doc this page summarises (from /raw/_manifest.json)
    cited_for: "What this source is the authority for"
source_type: transcript            # closed vocab value, see /raw/README.md
source_date: YYYY-MM-DD
related:
  - entities/EXAMPLE
  - concepts/EXAMPLE
status: active
last_updated: YYYY-MM-DD
last_ingest_event: log:YYYY-MM-DD-N
see_raw_for:                        # optional, for detail deliberately summarised out of the wiki
  - id: RAW_DOC_ID
    notes: "What lives only in raw"
---

One source page per ingested raw doc. It carries the LLM's summary, the key extracts, and where this source's content surfaces elsewhere in the wiki.

## Summary

Short synthesis of what this source establishes. Every factual claim cites its source ID inline, for example [a benchmark figure]^[src:RAW_DOC_ID]. Say so plainly when the source does not support a claim, rather than filling the gap.

## Key extracts

- [A material point from the source]^[src:RAW_DOC_ID]
- [Another material point]^[src:RAW_DOC_ID]

## Where this surfaces

Pages that draw on this source. The maintainer injects these WikiLinks with a regex pass after content generation.

- [[entities/EXAMPLE]]
- [[concepts/EXAMPLE]]
- [[decisions/EXAMPLE]]
