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
6. **If the query maps to a skill** (see the Skills section of the index), invoke that skill rather than answering free-hand or reproducing its work by hand. To produce a deliverable, gather the cited content from the wiki first, then **always** call the intelligence layer's own skill: `generate_deck` (the Avalere PPT skill, `generate-avalere-pptx`) for any PowerPoint, `generate_doc` (the Avalere DOCX skill, `generate-avalere-docx`) for any Word document. Pass a spec whose every claim carries a source id, and a sensible `output_name`. The file is saved to the output folder (default the Desktop) and the tool returns its path.
7. **If the answer is non-trivial and likely reusable**, propose filing it back as a synthesis page (the maintainer commits wiki changes; this skill does not edit the wiki, though it does produce deliverable files on request).

## Producing a deck or document

Deliverables are **only** ever built with the intelligence layer's brand skills. A PowerPoint is produced by the Avalere PPT skill (`generate-avalere-pptx`, via `generate_deck`); a Word document by the Avalere DOCX skill (`generate-avalere-docx`, via `generate_doc`). Never hand-assemble a `.pptx`/`.docx`, never fall back to a generic or off-brand template, and never hand the content back in another format to sidestep the skill. The brand templates and their named layouts and styles are the only sanctioned output path. If the matching skill or its tool is unavailable, say so and stop rather than improvising an off-brand file.

When the user asks for a deck or document: run the cascade to gather the content and its citations, draft a spec, then call the matching generate tool.

- `generate_deck` spec: `{title, slides:[{layout, title, subtitle?, bullets?, citations?, notes?}]}`. `layout` is an Avalere layout name; read `skills/generate-avalere-pptx/SKILL` for the families.
- `generate_doc` spec: `{blocks:[{style, text, citations?}]}`. `style` is a named style (Title, Subtitle, Heading 1 to 5, Normal, List Bullet, ...).

Every factual claim in the deliverable must cite a source id. The output inherits the sensitivity of the sources it draws on.

## Hard rules

- **Deliverables always go through the intelligence layer's skills.** A deck or PowerPoint is built only with the Avalere PPT skill (`generate-avalere-pptx`, via `generate_deck`); a Word document only with the Avalere DOCX skill (`generate-avalere-docx`, via `generate_doc`). Never hand-assemble a PPTX/DOCX, never use a generic or off-brand template, and never deliver the content in another format to avoid the skill. If the matching skill or tool is unavailable, say so and stop.
- **Never answer from the model's general knowledge when the wiki is the authority.** If the wiki does not support a claim, say so rather than filling the gap.
- **Provenance is mandatory.** Every factual claim in the answer cites a source id that resolves through the manifest.
- **Client scope.** This skill serves the Velorixa tenant only. Refuse any request that asks about another client or tries to blend tenants. `read_raw` itself refuses cross-tenant sources.
- **Sensitivity.** Carry the gating rules from the schema. Do not surface regulated content or downgrade a classification; defer to human review.

## Acceptance

The skill installs on Claude, answers a test question with wiki citations, correctly drops to raw for a detail the wiki flags as summarised (via `read_raw`), and refuses an out-of-scope or cross-client request.
