# Viewer (Phase 5)

Placeholder for the Next.js wiki viewer, deployed as a subdomain of nateclaw.com (default `intelligence.nateclaw.com`).

Planned per build prompt §7:

- Reads the wiki straight from this repo. Read-only and stateless.
- Renders markdown with frontmatter, resolves WikiLinks, shows backlinks, a graph view, and source preview on hover for `^[src:...]` citations.
- Renders skill-invocation buttons on pages that declare `available_skills`.
- Respects user-level permissions on confidential pages.

Not built yet. Phase 5 needs a host (Vercel or equivalent), DNS for the subdomain, and edit access to the nateclaw.com tile.
