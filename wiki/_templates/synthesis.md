---
title: TITLE
type: synthesis
client: velorixa
therapeutic_area: insomnia
sensitivity: client-confidential   # inherits the highest sensitivity of any cited source
sources:
  - id: RAW_DOC_ID_A
    cited_for: "First input"
  - id: RAW_DOC_ID_B
    cited_for: "Second input"
related:
  - concepts/EXAMPLE
  - projects/EXAMPLE
status: active
last_updated: YYYY-MM-DD
last_ingest_event: log:YYYY-MM-DD-N
---

LLM-generated comparison, analysis, contradiction, or evolving thesis, filed back as a reusable page rather than re-derived each query.

## Question

What this synthesis set out to answer.

## Analysis

The reasoning, with every claim traced to a source, for example [the first input's finding]^[src:RAW_DOC_ID_A]. Where sources disagree, state the disagreement and which source says what, for example [the conflicting finding]^[src:RAW_DOC_ID_B]. A contradiction across three or more sources is surfaced for human review, not resolved silently.

## Takeaway

The reusable conclusion.

## Inputs

- [[sources/EXAMPLE_A]]
- [[sources/EXAMPLE_B]]
