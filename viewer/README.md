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

## Confidentiality (why it is auth-gated)

The wiki is client-confidential, so the viewer must never serve to an
unauthenticated audience. The Worker enforces HTTP Basic Auth and **fails
closed**: if the `VIEWER_USER` / `VIEWER_PASS` secret bindings are absent it
returns 503 and serves nothing. Credentials live as Worker secrets, never in
code or git. Pages send `noindex` / `no-store` headers.

## Deployment

Deployed via the Cloudflare REST API (no `wrangler`, no Node):

- Worker / dashboard tile: `intelligence-layer-prototype-claude`
- URL: `https://intelligence-layer-prototype-claude.nateclaw0.workers.dev`
- Auth: HTTP Basic Auth; user `velorixa`, password held as a Worker secret.

Redeploy after editing the wiki:

1. `python3 viewer/build_viewer.py`
2. `PUT /accounts/{account_id}/workers/scripts/intelligence-layer-prototype-claude` with `worker.js` as the module and the `VIEWER_USER` / `VIEWER_PASS` secret_text bindings.

The custom domain `intelligence.nateclaw.com` is deferred: that hostname already
has externally-managed DNS records, so the viewer stays on its `workers.dev`
URL until the existing record is repointed.

## Not yet

- Backlinks panel, graph view, and citation hover-preview.
- Skill-invocation buttons on pages that declare `available_skills`.
- Cloudflare Access (SSO) in place of Basic Auth for per-user permissions.
