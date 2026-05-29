# MCP connector

The bridge that lets a Claude client query the Velorixa Intelligence Layer. It is a dependency-free stdio MCP server (Python 3.9+, no packages to install) that serves the wiki and the raw layer read-only and tenant-scoped.

## Tools

| Tool | Purpose |
|------|---------|
| `get_schema` | Read `CLAUDE.md` (rules + cascade). Call first. |
| `read_index` | Read `index.md` (catalogue). Call on every query. |
| `read_page` | Read a wiki page by path, e.g. `sources/2026-04-02-kickoff-brand-ambition`. |
| `search_wiki` | Case-insensitive search across pages, returns snippets. |
| `list_sources` | List raw sources from the manifest. |
| `resolve_source` | Resolve a cited `src:id` to its raw file metadata. |
| `read_raw` | Follow a source id into the raw original (drop-to-raw). Refuses cross-tenant. |

## Environment

| Var | Default |
|-----|---------|
| `WIKI_DIR` | `../../wiki` relative to the server |
| `RAW_MANIFEST` | the Drive `raw/_manifest.json` |
| `TENANT` | `velorixa` |

## Connect it to Claude Desktop

Add this to `~/Library/Application Support/Claude/claude_desktop_config.json` under `mcpServers` (see `claude_desktop_config.example.json`), then restart Claude Desktop. The wiki tools then appear in the app.

```json
{
  "mcpServers": {
    "velorixa-intelligence-layer": {
      "command": "python3",
      "args": ["/Users/Aitesting/Intelligence-Layer-Prototype-Claude/access-skill/mcp_server/server.py"],
      "env": {
        "WIKI_DIR": "/Users/Aitesting/Intelligence-Layer-Prototype-Claude/wiki",
        "RAW_MANIFEST": "/Users/Aitesting/Library/CloudStorage/GoogleDrive-nicolasgchr@gmail.com/.shortcut-targets-by-id/1QflKW2ZIKTW9ppldBWKpV0xwPK6Yjl04/Intelligence Layer Prototype_Claude_v1/raw/_manifest.json",
        "TENANT": "velorixa"
      }
    }
  }
}
```

## Connect it to Claude Code

```
claude mcp add velorixa-intelligence-layer -- python3 /Users/Aitesting/Intelligence-Layer-Prototype-Claude/access-skill/mcp_server/server.py
```

or commit a project `.mcp.json` with the same server block.

## Test it without a client

```
python3 - <<'PY' | python3 mcp_server/server.py
import json
for r in [
 {"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"t","version":"0"}}},
 {"jsonrpc":"2.0","id":2,"method":"tools/list"},
 {"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"read_index","arguments":{}}},
]: print(json.dumps(r))
PY
```

## For remote / multi-user access (later)

This local stdio server is the prototype. To let people off this machine query the layer, wrap the same tools behind a hosted HTTP/SSE MCP endpoint (a small service reading the repo and a synced copy of the manifest). The tool surface stays identical; only the transport changes.

## Notes

- Read-only. The connector never writes to the wiki or raw. Filing synthesis back is the maintainer's job.
- Path-traversal guarded: `read_page` is confined to `WIKI_DIR`, `read_raw` to the raw project folder.
- Tenant-scoped: `read_raw` refuses any source whose client is not `TENANT`.
