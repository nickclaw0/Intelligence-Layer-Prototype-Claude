# Connector-based access skill (Phase 8)

The browser-installable variant of the Velorixa Intelligence Layer access skill. It uses Claude's built-in **GitHub** and **Google Drive** connectors instead of a custom MCP server, so anyone with those two connectors enabled on claude.ai can install this skill and query the Intelligence Layer from a normal chat.

Compare with [`../access-skill/`](../access-skill/), which is the local stdio prototype (Phase 7). Same rules, same cascade, different transport.

## Contents

- [`SKILL.md`](SKILL.md) — the skill itself. The body is what Claude loads when the skill triggers.

## Install

### 1. Enable the connectors

On claude.ai → **Settings → Connectors**:

- Enable the **GitHub** connector and authorise it against the `nickclaw0/Intelligence-Layer-Prototype-Claude` repo (read-only is enough).
- Enable the **Google Drive** connector and authorise it against the Drive folder named `Intelligence Layer Prototype_Claude_v1` (read-only is enough).

### 2. Install the skill

On claude.ai → **Settings → Skills → Add skill**, upload `SKILL.md` (or a zip of this folder). The skill will appear as `velorixa-intelligence-layer` in your skill list.

### 3. Try it

Open a new chat and ask one of:

- _"What does the wiki say about the Velorixa brand ambition?"_
- _"What did we decide about positioning at the workshop?"_
- _"Show me the Velorixa source list."_

The skill should:

1. Fetch `wiki/CLAUDE.md` from GitHub.
2. Fetch `wiki/index.md`.
3. Read the relevant source page.
4. Reply with claims cited as `[claim]^[src:<id>]`.
5. State the inherited sensitivity classification.

## What it does (and does not)

The skill follows the same cascade and hard rules as the maintainer schema at `wiki/CLAUDE.md`:

- Reads the schema, then the index, then candidate pages from GitHub.
- Cites every factual claim with `[claim]^[src:<id>]`, where ids resolve through `raw/_manifest.json` in Drive.
- Drops to raw via the Drive connector only when the wiki flags `see_raw_for` or the question demands detail the wiki does not carry.
- Refuses any cross-tenant request and any raw source whose manifest `client` is not `velorixa`.
- Propagates sensitivity upward; surfaces the inherited classification when it is `client-confidential` or `regulated`.
- Escalates MLR-relevant content to a human.
- Read-only: never edits the wiki, the manifest, or any raw file.

## Not in scope for v1

- `generate_deck` / `generate_doc`. The Avalere deck and document generators are still available via the local stdio variant (`../access-skill/mcp_server/`). Adding them to the connector-based path needs a small hosted Python service and is a follow-up.
- Wiki writes. The maintainer agent on the repo handles those.

## Acceptance

See the "Acceptance" section in [`SKILL.md`](SKILL.md). Run it from a fresh chat after installing.
