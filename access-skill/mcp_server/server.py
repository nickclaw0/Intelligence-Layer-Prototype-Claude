#!/usr/bin/env python3
"""
Velorixa Intelligence Layer - MCP connector (Phase 7).

A dependency-free stdio MCP server (JSON-RPC 2.0, newline-delimited) that bridges
the wiki and the raw source-of-truth into a Claude (or any MCP) client, read-only
and tenant-scoped. It is the bridge the installable access skill reasons against,
so whichever interface a person uses, they hit the same wiki, provenance, and rules.

Runs on Python 3.9+ with no external packages.

Environment:
    WIKI_DIR       path to the wiki/ directory (default: ../../wiki relative to this file)
    RAW_MANIFEST   path to raw/_manifest.json (default: the Drive raw manifest)
    TENANT         client scope (default: velorixa)

Tools exposed (all read-only):
    get_schema, read_index, read_page, search_wiki,
    list_sources, resolve_source, read_raw
"""
import sys, os, json, glob, re, importlib.util

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.realpath(os.path.join(HERE, "..", ".."))
OUTPUT_DIR = os.path.realpath(os.environ.get("OUTPUT_DIR", os.path.expanduser("~/Desktop")))
WIKI_DIR = os.path.realpath(os.environ.get("WIKI_DIR", os.path.join(HERE, "..", "..", "wiki")))
RAW_MANIFEST = os.environ.get(
    "RAW_MANIFEST",
    "/Users/Aitesting/Library/CloudStorage/GoogleDrive-nicolasgchr@gmail.com/"
    ".shortcut-targets-by-id/1QflKW2ZIKTW9ppldBWKpV0xwPK6Yjl04/"
    "Intelligence Layer Prototype_Claude_v1/raw/_manifest.json",
)
RAW_ROOT = os.path.realpath(os.path.dirname(os.path.dirname(RAW_MANIFEST)))  # the project folder
TENANT = os.environ.get("TENANT", "velorixa")
PROTOCOL_DEFAULT = "2024-11-05"

# ---------------- helpers ----------------

def _safe_read(path, root):
    """Read a file only if it resolves inside root (path-traversal guard)."""
    rp = os.path.realpath(path)
    if not (rp == root or rp.startswith(root + os.sep)):
        raise ValueError(f"path escapes allowed root: {path}")
    if not os.path.exists(rp):
        raise FileNotFoundError(path)
    with open(rp, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _manifest():
    if not os.path.exists(RAW_MANIFEST):
        return {"sources": []}
    return json.load(open(RAW_MANIFEST, encoding="utf-8"))


def _resolve(mani, sid):
    for s in mani.get("sources", []):
        if sid == s.get("id") or sid == s.get("short_ref") or (len(sid) >= 6 and s.get("id", "").startswith(sid)):
            return s
    return None

# ---------------- tools ----------------

def t_get_schema(_):
    return _safe_read(os.path.join(WIKI_DIR, "CLAUDE.md"), WIKI_DIR)


def t_read_index(_):
    return _safe_read(os.path.join(WIKI_DIR, "index.md"), WIKI_DIR)


def t_read_page(args):
    rel = args.get("path", "")
    if not rel.endswith(".md"):
        rel += ".md"
    return _safe_read(os.path.join(WIKI_DIR, rel), WIKI_DIR)


def t_search_wiki(args):
    q = args.get("query", "").lower().strip()
    if not q:
        return "empty query"
    hits = []
    for p in glob.glob(os.path.join(WIKI_DIR, "**", "*.md"), recursive=True):
        txt = open(p, encoding="utf-8", errors="replace").read()
        if q in txt.lower():
            rel = os.path.relpath(p, WIKI_DIR)[:-3]
            idx = txt.lower().find(q)
            snippet = txt[max(0, idx - 60):idx + 80].replace("\n", " ")
            hits.append(f"[[{rel}]] … {snippet} …")
    return "\n".join(hits) if hits else "no matches"


def t_list_sources(_):
    mani = _manifest()
    out = []
    for s in mani.get("sources", []):
        out.append(f"{s.get('short_ref') or s.get('id','')[:8]}  {s.get('source_type')}  "
                   f"{s.get('classification')}  {s.get('original_filename')}")
    return "\n".join(out) if out else "no sources"


def t_resolve_source(args):
    s = _resolve(_manifest(), args.get("id", ""))
    if not s:
        return f"unresolved source id: {args.get('id')}"
    return json.dumps({k: s.get(k) for k in
                       ("id", "short_ref", "original_filename", "current_path",
                        "source_type", "classification", "client")}, indent=2)


def t_read_raw(args):
    """Follow a source id into the raw original (the cascade's drop-to-raw step)."""
    s = _resolve(_manifest(), args.get("id", ""))
    if not s:
        return f"unresolved source id: {args.get('id')}"
    if s.get("client", TENANT) != TENANT:
        return f"refused: source belongs to another client ({s.get('client')}); cross-tenant access is blocked"
    path = os.path.join(RAW_ROOT, s.get("current_path", ""))
    ext = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md", ".json", ".csv"):
        return _safe_read(path, RAW_ROOT)
    # binary formats: do not dump bytes; return locator + metadata
    return (f"binary source ({ext}). Original: {s.get('original_filename')} "
            f"[{s.get('source_type')}, {s.get('classification')}] at {s.get('current_path')}. "
            f"Use a document-extraction step to read its contents.")


def _load_module(rel_path, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(REPO_ROOT, rel_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _safe_out(name, ext):
    base = os.path.basename(name or "")
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", base) or ("velorixa_output" + ext)
    if not base.lower().endswith(ext):
        base += ext
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    return os.path.join(OUTPUT_DIR, base)


def t_generate_deck(args):
    spec = args.get("spec") or {}
    if isinstance(spec, str):
        spec = json.loads(spec)
    out = _safe_out(args.get("output_name", "velorixa_deck"), ".pptx")
    try:
        mod = _load_module("wiki/skills/generate-avalere-pptx/build_deck.py", "build_deck")
    except Exception as e:
        return f"deck engine unavailable: {e}. The engine is pure standard library; check that build_deck.py is present under wiki/skills/generate-avalere-pptx/."
    path, n = mod.build(spec, mod.DEFAULT_TEMPLATE, out)
    return f"Created deck: {path} ({n} slides) in the Avalere template. Open it from there."


def t_generate_doc(args):
    spec = args.get("spec") or {}
    if isinstance(spec, str):
        spec = json.loads(spec)
    out = _safe_out(args.get("output_name", "velorixa_doc"), ".docx")
    try:
        mod = _load_module("wiki/skills/generate-avalere-docx/build_doc.py", "build_doc")
    except Exception as e:
        return f"doc engine unavailable: {e}. The engine is pure standard library; check that build_doc.py is present under wiki/skills/generate-avalere-docx/."
    path, n = mod.build(spec, mod.DEFAULT_TEMPLATE, out)
    return f"Created document: {path} ({n} blocks) in the Avalere template. Open it from there."


TOOLS = [
    {"name": "get_schema", "description": "Read CLAUDE.md, the maintainer schema and query rules. Read this first.",
     "inputSchema": {"type": "object", "properties": {}}, "fn": t_get_schema},
    {"name": "read_index", "description": "Read index.md, the wiki catalogue. Read on every query.",
     "inputSchema": {"type": "object", "properties": {}}, "fn": t_read_index},
    {"name": "read_page", "description": "Read a wiki page by path relative to wiki/ (e.g. 'sources/2026-04-02-kickoff-brand-ambition').",
     "inputSchema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}, "fn": t_read_page},
    {"name": "search_wiki", "description": "Case-insensitive search across wiki pages; returns matching pages with snippets.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}, "fn": t_search_wiki},
    {"name": "list_sources", "description": "List raw sources from the manifest (id, type, classification, filename).",
     "inputSchema": {"type": "object", "properties": {}}, "fn": t_list_sources},
    {"name": "resolve_source", "description": "Resolve a cited source id to its raw file metadata via the manifest.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}, "fn": t_resolve_source},
    {"name": "read_raw", "description": "Follow a source id into the raw original (cascade drop-to-raw). Tenant-scoped.",
     "inputSchema": {"type": "object", "properties": {"id": {"type": "string"}}, "required": ["id"]}, "fn": t_read_raw},
    {"name": "generate_deck",
     "description": "Build an on-brand Avalere PowerPoint from wiki content and save it (default ~/Desktop). "
                    "spec: {title, slides:[{layout, title, subtitle?, bullets?, citations?, notes?}]}. "
                    "layout is an Avalere layout name (read skills/generate-avalere-pptx/SKILL for families). Cite every claim.",
     "inputSchema": {"type": "object", "properties": {
         "spec": {"type": "object", "description": "Deck spec with a slides list."},
         "output_name": {"type": "string", "description": "Output filename, saved to the output folder."}},
         "required": ["spec"]}, "fn": t_generate_deck},
    {"name": "generate_doc",
     "description": "Build an on-brand Avalere Word document from wiki content and save it (default ~/Desktop). "
                    "spec: {blocks:[{style, text, citations?}]}. style is a named style (Title, Heading 1, Normal, List Bullet, ...). Cite every claim.",
     "inputSchema": {"type": "object", "properties": {
         "spec": {"type": "object", "description": "Document spec with a blocks list."},
         "output_name": {"type": "string", "description": "Output filename, saved to the output folder."}},
         "required": ["spec"]}, "fn": t_generate_doc},
]
TOOL_BY_NAME = {t["name"]: t for t in TOOLS}

# ---------------- JSON-RPC stdio loop ----------------

def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def handle(req):
    method = req.get("method")
    rid = req.get("id")
    if method == "initialize":
        ver = (req.get("params") or {}).get("protocolVersion", PROTOCOL_DEFAULT)
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "protocolVersion": ver,
            "capabilities": {"tools": {}},
            "serverInfo": {"name": "velorixa-intelligence-layer", "version": "1.0.0"},
        }}
    if method in ("notifications/initialized", "notifications/cancelled"):
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {
            "tools": [{"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]} for t in TOOLS]
        }}
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = TOOL_BY_NAME.get(name)
        if not tool:
            return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"unknown tool: {name}"}}
        try:
            text = tool["fn"](args)
            return {"jsonrpc": "2.0", "id": rid, "result": {"content": [{"type": "text", "text": text}]}}
        except Exception as e:
            return {"jsonrpc": "2.0", "id": rid,
                    "result": {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}}
    if rid is not None:
        return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"method not found: {method}"}}
    return None


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(req)
        if resp is not None:
            send(resp)


if __name__ == "__main__":
    main()
