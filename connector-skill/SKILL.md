---
name: velorixa-intelligence-layer
description: Query the Velorixa Intelligence Layer wiki (Layer 1) with provenance, sensitivity gating, and tenant scope, using the GitHub and Google Drive connectors. Cite every claim. Refuse cross-tenant requests.
triggers:
  - query_patterns: ["velorixa", "VLX", "the intelligence layer", "the wiki", "what did we decide", "what does the wiki say"]
required_connectors:
  - github
  - google_drive
client: velorixa
sensitivity: inherits_from_wiki
---

# Velorixa Intelligence Layer access skill

This skill lets you query the Velorixa Intelligence Layer wiki (Layer 1, in GitHub) and drop to its raw sources (Layer 0, in Google Drive) when needed. It is the browser-installable, connector-based variant of `access-skill/`. Same rules, same cascade, different transport.

The schema at `wiki/CLAUDE.md` is the highest-weight document in the system. Load it at session start and follow it verbatim. When this skill body and the loaded schema disagree, the schema wins.

## Where things live

- **Wiki (Layer 1)**: GitHub repo `nickclaw0/Intelligence-Layer-Prototype-Claude`, branch `main`. Read with the GitHub connector.
- **Raw (Layer 0) and the manifest**: the Google Drive folder named `Intelligence Layer Prototype_Claude_v1`, specifically the `raw/` subtree. The manifest is at `raw/_manifest.json`. Read with the Google Drive connector.

If either location is missing or you cannot read it, stop and report the missing location. Do not guess and do not answer from general knowledge.

## The query cascade (run in order)

1. **Read the schema first.** Use the GitHub connector to fetch `wiki/CLAUDE.md` from `nickclaw0/Intelligence-Layer-Prototype-Claude`. Apply its rules to everything that follows. If the file is missing, stop.
2. **Read the index.** Fetch `wiki/index.md` from the same repo. The index enumerates the wiki: entities, concepts, sources, projects, synthesis, decisions, skills.
3. **Identify candidate pages.** Pick the entity, concept, project, synthesis, and source pages the query touches. When the query word does not appear in the index, fall back to GitHub code search across the repo to find pages that reference it.
4. **Read the candidate pages.** Fetch each with the GitHub connector.
5. **Answer with citations.** Every factual claim in the response cites a source id, in the inline form `[claim]^[src:<id>]`. Source ids are the manifest keys (sha256 content hashes for now; Drive file ids once Phase 3 reconciles). Keep house style: plain and conversational, no em dashes, no "X is not just Y" construction, no forced three-item lists.
6. **Drop to raw only when the wiki summarises and points there**, or when the question demands detail the wiki does not carry. Procedure:
   1. Use the Drive connector to read `raw/_manifest.json` inside the `Intelligence Layer Prototype_Claude_v1` folder.
   2. Find the manifest entry whose `id` (or `short_ref`) matches the citation.
   3. Confirm the entry's `client` field is `velorixa`. If it is anything else, refuse and stop. The tenant guard rejects cross-client access.
   4. Use the Drive connector to read the file at `current_path` (search by basename inside the project folder; the filesystem is case-insensitive). Integrate the original detail into the answer using the same `^[src:<id>]` citation.
7. **If the answer is non-trivial and likely reusable**, say so plainly so a human can decide whether to file it back as a synthesis page. Do not edit the wiki yourself.

Most queries resolve at step 5. Drop to raw only when needed.

## Hard rules

These mirror `wiki/CLAUDE.md`. The schema you load at step 1 is authoritative.

- **Provenance is mandatory.** Every factual claim cites a source id with `[claim]^[src:<id>]`. If a claim cannot trace to a manifest entry, say so plainly. Do not fill the gap from general knowledge.
- **Single tenant.** This skill serves the Velorixa tenant only. Refuse any request that names another client, asks to compare across clients, or tries to blend tenants. Refuse any raw source whose manifest `client` is not `velorixa`.
- **Sensitivity gating.** Classifications are `public`, `internal`, `client-confidential`, `regulated`. Sensitivity propagates upward: a response inherits the highest classification of any source it cites. State the inherited classification when it is `client-confidential` or `regulated`. Never surface `regulated` material without explicit human approval recorded in `wiki/log.md`.
- **MLR escalation.** Anything medical, legal, or regulatory pauses for human review. Do not answer free-hand. Surface the question and stop.
- **Off-label and safety.** Never extrapolate beyond approved indications. Never invent efficacy claims. Never aggregate safety data without explicit human approval. When uncertain about a safety or claims question, escalate by default.
- **Contradictions.** If new material contradicts three or more existing sources, surface the contradiction for human review rather than resolving it.
- **Read-only.** This skill never edits the wiki, the manifest, or any raw file. The maintainer agent (separate, on the repo) commits wiki changes.

## House style

Plain and conversational. No em dashes. Avoid the "X is not just Y" construction. Do not force three-item lists. Prefer the source's wording over heavy paraphrase. Attribute client statements to the client; keep agency voice and client voice clearly separated.

## Acceptance

The skill is correctly installed and behaving when, in a fresh chat:

1. It loads the GitHub connector, fetches `wiki/CLAUDE.md`, and follows the cascade.
2. It answers a wiki-supported question (for example, "what was the kickoff brand ambition?") with at least one `[claim]^[src:<id>]` citation, with no claim left uncited.
3. For a question that needs raw detail beyond the source page summary, it uses the Drive connector to fetch `raw/_manifest.json`, resolves the id, confirms the entry's `client` is `velorixa`, reads the file, and integrates the detail with the same citation.
4. It refuses a request that names another client, and refuses to downgrade a classification.

## Not in scope for v1

- `generate_deck` and `generate_doc`. The Avalere deck and document generators rely on `python-pptx` and `python-docx` and remain in the local stdio variant under `access-skill/mcp_server/`. The connector-based skill is read-only for now and will gain deliverable generation in a later iteration that wraps a small hosted service.
- Wiki edits. Filing synthesis back is the maintainer's job, not this skill's.
