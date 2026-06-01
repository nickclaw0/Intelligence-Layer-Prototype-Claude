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
| 3 | n8n ingest pipeline | seed batch filed: 31 raw sources in Drive + manifest (`ingest/file_seed_batch.py`); go-forward workflow **created live** in the n8n instance via the public API (`Intelligence Layer Prototype Claude`, id `DtkNEcdolxsSIpHs`, inactive); Drive OAuth on its 5 Drive nodes + the `REPLACE_WITH_*` IDs/PAT + a manual test remain before activation (see `ingest/README.md`) |
| 4 | Skills / Avalere generators (Layer 3) | done; five skills under `wiki/skills/`, engines are pure standard library (zipfile + xml.etree, no pip installs on Python 3.9), all pass `skill_test.py all` and `skill_creator.py lint all`, and `build_deck.py` / `build_doc.py` produce valid on-brand PPTX/DOCX from the pinned Avalere templates |
| 5 | Wiki viewer | built + deployed (auth-gated Cloudflare Worker); Obsidian-style association graph; custom domain `intelligence-layer.nateclaw.com`; auto-resyncs from the wiki via the daily lint |
| 6 | Lint | `daily_lint.py` (incremental) + `full_sweep.py` (whole-wiki); scheduled as the remote Claude routine `velorixa-daily-lint` (id `trig_014bDabKh7nT66xBbvPbJhVH`, 05:00 UTC daily) — pending a GitHub re-auth so the cloud env can clone the repo (see `lint/routine.md`) |
| 7 | Installable access skill + MCP connector | done (`access-skill/`, `connector-skill/`); plus self-contained, installable Avalere generator skills for Claude.ai (`generate-avalere-pptx`, `generate-avalere-docx`), each bundling its engine + pinned template to run in code execution with no install step |

## Open items (handoff)

What a maintainer picking this up should know is outstanding, as of 2026-06-01:

- **n8n ingest pipeline — created, not yet live.** The workflow `Intelligence Layer Prototype Claude` (id `DtkNEcdolxsSIpHs`) exists in the n8n instance, inactive. Before activating: attach a Google Drive OAuth credential to its 5 Drive nodes (trigger + 4 actions), fill the four `REPLACE_WITH_*` values (three Drive IDs + a GitHub fine-grained PAT with `contents:write`), run one manual test, then activate. Step-by-step in `ingest/README.md`.
- **Daily lint — scheduled, blocked on GitHub auth.** The remote Claude routine `velorixa-daily-lint` (id `trig_014bDabKh7nT66xBbvPbJhVH`, 05:00 UTC daily, NateClaw cloud env) is created and enabled, but a verification run returned `github_repo_access_denied`. Re-authorize the Claude GitHub App for `nickclaw0/Intelligence-Layer-Prototype-Claude` on that environment, then trigger a run to confirm. Because it runs in the cloud it reads the Drive manifest via the Google Drive connector and does **not** redeploy the viewer (no Cloudflare token in the cloud env) — viewer resync stays local, via `viewer/deploy_viewer.py` or the local lint hook.
- **Homepage tile — staged, not deployed.** The `nateclaw.com` homepage source (`index.html`, in Drive under `NateClaw.com/i-want-you-to-create-a/`) has a live tile for this viewer (→ `intelligence-layer.nateclaw.com`). It goes live on the next `node deploy-cloudflare.mjs` run. That homepage Worker also bundles the dashboards and the separate Codex viewer, so it is redeployed deliberately with that tested Node tooling, not by hand.
- **Installable skill bundles on Drive.** Zips sit in the Drive project folder for installing into Claude.ai: `velorixa-intelligence-layer-skill.zip` (the wiki query skill = `connector-skill/SKILL.md`), the PPT generator, and `velorixa-avalere-docx-skill.zip`. The PPT generator ships in two shapes: **slim** `velorixa-avalere-pptx-skill.zip` (~10 KB) carries only the engine and SKILL.md — at first build the engine pulls the pinned template from the public repo over `raw.githubusercontent.com`, so it never drifts but needs the sandbox to allow that egress; **offline** `velorixa-avalere-pptx-skill-offline.zip` (~3.5 MB) embeds the template under `assets/` and needs no network. The DOCX bundle (~88 KB) embeds its template directly since it is small. The engines resolve the template in order: a co-located `assets/<template>` (bundle), then `../_assets/` (repo), then a one-time download from the public repo cached under the temp dir (override the source with `AVALERE_PPTX_TEMPLATE_URL` / `AVALERE_DOCX_TEMPLATE_URL`). All bundles are snapshots: if a generator engine or SKILL.md changes in the repo, re-export the affected bundle (zip the skill folder with SKILL.md at the root, plus `assets/<template>` for the offline/embedded variants) so the installed skill does not drift.

## Conventions

- The maintainer cites every claim by raw source ID, resolved through `/raw/_manifest.json` in Drive. Citations use the inline form `[claim]^[src:<id>]`.
- Cross-links use Obsidian-compatible WikiLinks, for example `[[entities/velorixa]]`.
- Raw is immutable. The wiki references raw by ID, never by path, so a rename never orphans a citation.
- House style for authored prose: plain and conversational, no em dashes, no "X is not just Y", no forced three-item lists.

See `wiki/CLAUDE.md` for the full set of enforceable maintainer rules.
