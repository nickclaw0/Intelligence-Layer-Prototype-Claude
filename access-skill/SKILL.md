---
name: velorixa-intelligence-layer
description: Query the Velorixa Intelligence Layer from your everyday assistant, answering only from the wiki with citations
triggers:
  - query_patterns: ["velorixa", "the intelligence layer", "what did we decide", "what does the wiki say"]
required_tools:
  - get_schema
  - read_index
  - read_page
  - search_wiki
  - resolve_source
  - read_raw
  - generate_deck
  - generate_doc
outputs:
  - cited_answer
  - deck.pptx
  - document.docx
sensitivity: inherits_from_wiki
client: velorixa
---

The installable access skill. It lets anyone query the Velorixa Intelligence Layer from their day-to-day assistant. Whichever interface a person uses, they reason against the same wiki, with the same provenance, citations, and schema-enforced behaviour. It is paired with the MCP connector in `mcp_server/`, which exposes the wiki and raw layer as the tools named above.

## The query cascade (follow in order)

1. **Read the schema** with `get_schema` at the start of a session. It carries the rules: provenance, sensitivity gating, client scope.
2. **Read the index** with `read_index` on every query.
3. **Identify candidate pages** (entity, concept, project, synthesis, source) from the index and from `search_wiki`, and read them with `read_page`.
4. **If the wiki fully supports the answer, respond with citations** and stop. Cite every claim with its source id, the same `[src:id]` ids the pages carry.
5. **If a cited claim needs more depth than the wiki holds**, follow its source id into raw: `resolve_source` to find the file, then `read_raw` to read the original, and integrate.
6. **If the query maps to a skill** (see the Skills section of the index), invoke that skill rather than answering free-hand. To produce a deliverable, gather the cited content from the wiki first, then call `generate_deck` (Avalere PowerPoint) or `generate_doc` (Avalere Word). Pass a spec whose every claim carries a source id, and a sensible `output_name`. The file is saved to the output folder (default the Desktop) and the tool returns its path.
7. **If the answer is non-trivial and likely reusable**, propose filing it back as a synthesis page (the maintainer commits wiki changes; this skill does not edit the wiki, though it does produce deliverable files on request).

## Producing a deck or document

When the user asks for a deck or document: run the cascade to gather the content and its citations, draft a spec, then call the matching generate tool.

- `generate_deck` spec: `{title, slides:[{layout, title, subtitle?, bullets?, citations?, notes?}]}`. `layout` is an Avalere layout name; read `skills/generate-avalere-pptx/SKILL` for the families.
- `generate_doc` spec: `{blocks:[{style, text, citations?}]}`. `style` is a named style (Title, Subtitle, Heading 1 to 5, Normal, List Bullet, ...).

Every factual claim in the deliverable must cite a source id. The output inherits the sensitivity of the sources it draws on.

## Hard rules

- **Never answer from the model's general knowledge when the wiki is the authority.** If the wiki does not support a claim, say so rather than filling the gap.
- **Provenance is mandatory.** Every factual claim in the answer cites a source id that resolves through the manifest.
- **Client scope.** This skill serves the Velorixa tenant only. Refuse any request that asks about another client or tries to blend tenants. `read_raw` itself refuses cross-tenant sources.
- **Sensitivity.** Carry the gating rules from the schema. Do not surface regulated content or downgrade a classification; defer to human review.

## Acceptance

The skill installs on Claude, answers a test question with wiki citations, correctly drops to raw for a detail the wiki flags as summarised (via `read_raw`), and refuses an out-of-scope or cross-client request.
