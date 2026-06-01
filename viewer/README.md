# Viewer (Phase 5)

A read-only wiki viewer, built node-free and deployed as a Cloudflare Worker.

Because the prototype environment has no Node toolchain, the viewer is **not**
Next.js. Instead `build_viewer.py` renders the wiki markdown straight from this
repo into a single self-contained Worker (`worker.js`) with a minimal,
dependency-free markdown renderer. Same goal as the planned Next.js viewer,
different transport.

## Files

- [`build_viewer.py`](build_viewer.py) — node-free generator. Reads `wiki/**/*.md`, parses frontmatter, renders HTML, builds the nav, and emits `worker.js`. Run it to rebuild; do not hand-edit `worker.js`.
- `worker.js` — generated build artifact (gitignored). Regenerate with `python3 viewer/build_viewer.py`.

## What it does

- Reads the wiki from this repo. Read-only and stateless.
- Renders markdown with frontmatter, resolves WikiLinks to internal links, and styles `^[src:...]` citations.
- Shows each page's type, client, and sensitivity as tags; flags `client-confidential` and `regulated` pages.
- Groups the nav by page type (schema, index, sources, synthesis, skills, log, and the entity/concept/project/decision sections as they fill in).
- The landing route (`/` and `/graph`) is an Obsidian-style association graph: a self-contained, dependency-free SVG force simulation where nodes are wiki pages and edges are the links between them (WikiLinks, `related:`, and `^[src:...]` citations resolved to their source page). Node size scales with connection count, hover highlights neighbours, drag pins a node, scroll zooms, and clicking a node opens the page. The `index` is kept as a node but contributes no outbound edges, so it stays present without dominating the layout; unresolved link targets render as distinct hollow nodes.

## Access

The viewer is public by site owner request. Do not re-add HTTP Basic Auth or
`VIEWER_USER` / `VIEWER_PASS` bindings when redeploying. Pages still send
`noindex` / `no-store` headers.

## Deployment

Deployed via the Cloudflare REST API (no `wrangler`, no Node):

- Worker / dashboard tile: `intelligence-layer-prototype-claude`
- workers.dev URL: `https://intelligence-layer-prototype-claude.nateclaw0.workers.dev`
- Custom domain: `https://intelligence-layer.nateclaw.com`
- Auth: none. Both URLs route to the same Worker without a username/password prompt.

Redeploy after editing the wiki:

1. `python3 viewer/build_viewer.py`
2. `PUT /accounts/{account_id}/workers/scripts/intelligence-layer-prototype-claude` with `worker.js` as the module and no Basic Auth bindings.

Or do both in one step with the deploy helper, which reads the API token from
the environment:

```
CF_API_TOKEN=<token> python3 viewer/deploy_viewer.py
```

## Staying in sync with the wiki

The viewer is a static bake — it does not read the wiki at request time (no Node,
and the wiki lives in a private repo the Worker cannot reach). So "the graph
always reflects the wiki" means rebuild + redeploy whenever the wiki changes.
`viewer/deploy_viewer.py` is the node-free rebuild-and-PUT used for that, and the
daily lint (`lint/daily_lint.py`) calls it automatically after any run that
changed the wiki, gated on `VIEWER_AUTODEPLOY` + `CF_API_TOKEN` (see
`lint/routine.md`). A deploy failure is reported in the lint log line but never
fails the lint. The end-to-end chain is: Drive ingest -> daily lint folds new
sources -> viewer redeploys.

The custom domain is `intelligence-layer.nateclaw.com`. The first-choice
hostname `intelligence.nateclaw.com` already had an externally-managed DNS
record, so rather than repoint or overwrite it the viewer was attached on a
fresh, non-colliding subdomain. The Workers custom-domain attach
(`PUT /accounts/{account_id}/workers/domains`) self-protects: it refuses if the
hostname already has a DNS record, and on success it creates its own proxied
record. Attaching `intelligence-layer.nateclaw.com` added one new record and
left all pre-existing records (`intelligence`, `dashboard2`, `dashboard3`,
`www`, apex, and the TXT/`_domainconnect` entries) byte-for-byte unchanged.

## Not yet

- Backlinks panel and citation hover-preview. (The association graph view is done.)
- Skill-invocation buttons on pages that declare `available_skills`.
- Cloudflare Access (SSO) in place of Basic Auth for per-user permissions.
