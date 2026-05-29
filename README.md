# Intelligence Layer Prototype — Claude stack

The Git home of the Velorixa Intelligence Layer wiki (Layer 1) and viewer. This is the compounding artifact of the Living Intelligence Layer prototype. The raw source-of-truth layer (Layer 0) lives in Google Drive, not here.

Tenant: Velorixa (client code `VLX`), therapeutic area insomnia, project `launch-prep`. Single tenant, structured so a second could be stood up later with hard isolation.

## Layout

```
wiki/
  index.md          catalogue, read first on every query
  log.md            append-only audit trail
  CLAUDE.md         the maintainer agent's schema document (system prompt)
  entities/         clients, brands, products, competitors, KOLs, regulators, stakeholders
  concepts/         mechanisms, market dynamics, regulatory frameworks, creative platforms
  sources/          one page per ingested raw doc, with summary and key extracts
  projects/         one page per active engagement
  synthesis/        LLM-generated comparisons, analyses, theses, filed back as reusable pages
  decisions/        what was chosen, what was rejected, who decided
  skills/           SKILL.md files (Layer 3, authored in Phase 4)
  _templates/       one frontmatter-led template per page type
ingest/             Phase 3 ingest: n8n pipeline template + file_seed_batch.py (bootstrap filer that routed the seed batch into raw/ + manifest)
lint/               Phase 6 lint: daily incremental (daily_lint.py, optional viewer auto-deploy) + whole-wiki full sweep (full_sweep.py)
viewer/             Phase 5 read-only viewer, node-free Cloudflare Worker, auth-gated; association graph; deploy_viewer.py rebuild+redeploy
access-skill/       Phase 7 local stdio MCP server variant of the access skill
connector-skill/    browser-installable access skill on the GitHub + Google Drive connectors
```

## Phase status

| Phase | What | State |
| --- | --- | --- |
| 1 | Raw / ingest convention (Layer 0, Drive) | done |
| 2 | Wiki scaffold (Layer 1) | done |
| 3 | n8n ingest pipeline | seed batch filed: 31 raw sources in Drive + manifest (`ingest/file_seed_batch.py`); n8n template in `ingest/` for go-forward, live import needs instance URL + interactive credentials |
| 4 | Skills / Avalere generators (Layer 3) | done |
| 5 | Wiki viewer | built + deployed (auth-gated Cloudflare Worker); Obsidian-style association graph; custom domain `intelligence-layer.nateclaw.com`; auto-resyncs from the wiki via the daily lint |
| 6 | Lint | `daily_lint.py` (incremental) + `full_sweep.py` (whole-wiki); scheduling is per-environment |
| 7 | Installable access skill + MCP connector | done (`access-skill/`, `connector-skill/`) |

## Conventions

- The maintainer cites every claim by raw source ID, resolved through `/raw/_manifest.json` in Drive. Citations use the inline form `[claim]^[src:<id>]`.
- Cross-links use Obsidian-compatible WikiLinks, for example `[[entities/velorixa]]`.
- Raw is immutable. The wiki references raw by ID, never by path, so a rename never orphans a citation.
- House style for authored prose: plain and conversational, no em dashes, no "X is not just Y", no forced three-item lists.

See `wiki/CLAUDE.md` for the full set of enforceable maintainer rules.
