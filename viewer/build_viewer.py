#!/usr/bin/env python3
"""Node-free wiki viewer generator (Phase 5).

Reads the wiki markdown straight from this repo and renders a single
self-contained Cloudflare Worker (ES module) that serves a read-only,
auth-gated viewer. No Node, no build step, pure stdlib.

Confidentiality: the wiki is client-confidential, so the generated Worker
enforces HTTP Basic Auth and fails CLOSED (503) when its credential binding
is absent. Nothing is served unauthenticated.

Usage:
    python3 viewer/build_viewer.py            # writes viewer/worker.js
"""
import html
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WIKI = REPO / "wiki"
OUT = REPO / "viewer" / "worker.js"

SECTION_ORDER = [
    ("schema", "Schema"),
    ("index", "Index"),
    ("sources", "Sources"),
    ("synthesis", "Synthesis"),
    ("entities", "Entities"),
    ("concepts", "Concepts"),
    ("projects", "Projects"),
    ("decisions", "Decisions"),
    ("skills", "Skills"),
    ("log", "Log"),
]

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def split_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return {}, text
    fm_raw = m.group(1)
    body = text[m.end():]
    fm = {}
    for line in fm_raw.splitlines():
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm, body


# ---- minimal markdown -> html (line based) -------------------------------

INLINE_CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
ITALIC_RE = re.compile(r"(?<![\*])\*([^*]+)\*(?![\*])")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
CITE_RE = re.compile(r"\^?\[src:([^\]]+)\]")


def inline(text):
    # Order matters: protect code spans first.
    placeholders = {}

    def stash(m):
        key = f"\x00{len(placeholders)}\x00"
        placeholders[key] = "<code>" + html.escape(m.group(1)) + "</code>"
        return key

    text = INLINE_CODE_RE.sub(stash, text)
    text = html.escape(text)
    # citations -> styled sup (before generic links)
    text = CITE_RE.sub(lambda m: f'<sup class="cite" title="source {m.group(1)}">[src:{m.group(1)}]</sup>', text)
    # wikilinks -> internal links
    text = WIKILINK_RE.sub(lambda m: f'<a class="wl" href="/p/{m.group(1).strip()}">{m.group(1).strip()}</a>', text)
    # markdown links (note: html.escape turned & etc, urls here are simple)
    text = LINK_RE.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    text = BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = ITALIC_RE.sub(r"<em>\1</em>", text)
    for k, v in placeholders.items():
        text = text.replace(k, v)
    return text


def md_to_html(body):
    lines = body.splitlines()
    out = []
    i = 0
    in_code = False
    code_buf = []
    list_stack = []  # 'ul' or 'ol'

    def close_lists():
        while list_stack:
            out.append(f"</{list_stack.pop()}>")

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            if in_code:
                out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
                code_buf = []
                in_code = False
            else:
                close_lists()
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        stripped = line.strip()
        if not stripped:
            close_lists()
            i += 1
            continue

        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        if h:
            close_lists()
            level = len(h.group(1))
            out.append(f"<h{level}>{inline(h.group(2))}</h{level}>")
            i += 1
            continue

        if stripped == "---":
            close_lists()
            out.append("<hr>")
            i += 1
            continue

        ul = re.match(r"^(\s*)[-*]\s+(.*)$", line)
        ol = re.match(r"^(\s*)\d+\.\s+(.*)$", line)
        if ul or ol:
            want = "ul" if ul else "ol"
            if not list_stack or list_stack[-1] != want:
                close_lists()
                out.append(f"<{want}>")
                list_stack.append(want)
            content = (ul or ol).group(2)
            out.append(f"<li>{inline(content)}</li>")
            i += 1
            continue

        if stripped.startswith(">"):
            close_lists()
            out.append(f"<blockquote>{inline(stripped[1:].strip())}</blockquote>")
            i += 1
            continue

        # paragraph: gather consecutive plain lines
        close_lists()
        para = [stripped]
        j = i + 1
        while j < len(lines) and lines[j].strip() and not re.match(r"^(#{1,6}\s|\s*[-*]\s|\s*\d+\.\s|>|```)", lines[j]) and lines[j].strip() != "---":
            para.append(lines[j].strip())
            j += 1
        out.append("<p>" + inline(" ".join(para)) + "</p>")
        i = j
    if in_code:
        out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
    close_lists()
    return "\n".join(out)


def node_id(p):
    return str(p.relative_to(WIKI).with_suffix(""))


def section_of(nid):
    if nid == "CLAUDE":
        return "schema"
    if nid == "index":
        return "index"
    if nid == "log":
        return "log"
    top = nid.split("/")[0]
    return top if top in dict(SECTION_ORDER) else "other"


def build_pages():
    pages = {}
    for p in sorted(WIKI.rglob("*.md")):
        rel = p.relative_to(WIKI)
        if rel.parts[0] == "_templates":
            continue
        nid = node_id(p)
        fm, body = split_frontmatter(p.read_text())
        title = fm.get("title") or nid.split("/")[-1].replace("-", " ")
        pages[nid] = {
            "id": nid,
            "title": title,
            "type": fm.get("type", section_of(nid)),
            "sensitivity": fm.get("sensitivity", ""),
            "client": fm.get("client", ""),
            "html": md_to_html(body),
        }
    return pages


def build_nav(pages):
    nav = []
    for key, label in SECTION_ORDER:
        entries = []
        for nid, pg in pages.items():
            sec = section_of(nid)
            if sec != key:
                continue
            # skills: only list SKILL pages at top level
            if key == "skills" and not nid.endswith("/SKILL"):
                continue
            entries.append({"id": nid, "title": pg["title"]})
        if entries:
            nav.append({"label": label, "entries": sorted(entries, key=lambda e: e["id"])})
    return nav


def main():
    pages = build_pages()
    nav = build_nav(pages)
    data = {"pages": pages, "nav": nav}
    payload = json.dumps(data, ensure_ascii=False)
    worker = WORKER_TEMPLATE.replace("__DATA__", payload)
    OUT.write_text(worker)
    n_conf = sum(1 for p in pages.values() if "confidential" in p["sensitivity"] or "regulated" in p["sensitivity"])
    print(f"built {OUT.relative_to(REPO)}: {len(pages)} page(s), {len(nav)} section(s), "
          f"{n_conf} confidential/regulated page(s) gated behind Basic Auth")


WORKER_TEMPLATE = r"""// Velorixa Intelligence Layer viewer (Phase 5) -- generated by viewer/build_viewer.py
// Read-only, auth-gated. Serves client-confidential content; fails CLOSED.
const DATA = __DATA__;

const STYLE = `
  :root{--ink:#1a1a2e;--mut:#6b7280;--line:#e5e7eb;--accent:#0f766e;--warn:#b45309;--bg:#fafafa}
  *{box-sizing:border-box}
  body{margin:0;font:15px/1.6 -apple-system,Inter,Segoe UI,sans-serif;color:var(--ink);background:var(--bg)}
  .banner{background:#7f1d1d;color:#fff;padding:6px 16px;font-size:12px;letter-spacing:.02em;text-align:center}
  .wrap{display:flex;min-height:100vh}
  nav{width:280px;border-right:1px solid var(--line);padding:18px 16px;background:#fff;overflow-y:auto;height:100vh;position:sticky;top:0}
  nav h1{font-size:15px;margin:0 0 4px}
  nav .sub{color:var(--mut);font-size:12px;margin-bottom:16px}
  nav .sec{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:16px 0 6px}
  nav a{display:block;color:var(--ink);text-decoration:none;padding:3px 6px;border-radius:5px;font-size:13px}
  nav a:hover{background:#f1f5f9}
  nav a.active{background:#ecfdf5;color:var(--accent);font-weight:600}
  main{flex:1;padding:32px 48px;max-width:880px}
  main h1{margin-top:0}
  .meta{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 20px}
  .tag{font-size:11px;padding:2px 8px;border-radius:999px;background:#f1f5f9;color:var(--mut)}
  .tag.conf{background:#fef3c7;color:var(--warn)}
  .tag.reg{background:#fee2e2;color:#991b1b}
  sup.cite{color:var(--accent);font-weight:600;cursor:help}
  a.wl{color:var(--accent);text-decoration:none;border-bottom:1px dotted var(--accent)}
  pre{background:#0f172a;color:#e2e8f0;padding:14px;border-radius:8px;overflow:auto;font-size:13px}
  code{background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:13px}
  pre code{background:none;padding:0}
  blockquote{border-left:3px solid var(--line);margin:0;padding:4px 16px;color:var(--mut)}
  hr{border:none;border-top:1px solid var(--line);margin:24px 0}
  table{border-collapse:collapse}
`;

function esc(s){return s.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

function navHtml(active){
  let h = `<h1>Velorixa Intelligence Layer</h1><div class="sub">Layer 1 wiki &middot; read-only</div>`;
  for(const sec of DATA.nav){
    h += `<div class="sec">${esc(sec.label)}</div>`;
    for(const e of sec.entries){
      const cls = e.id===active ? "active":"";
      h += `<a class="${cls}" href="/p/${encodeURI(e.id)}">${esc(e.title)}</a>`;
    }
  }
  return `<nav>${h}</nav>`;
}

function pageHtml(id){
  const pg = DATA.pages[id];
  if(!pg) return null;
  let tags = "";
  if(pg.type) tags += `<span class="tag">${esc(pg.type)}</span>`;
  if(pg.client) tags += `<span class="tag">${esc(pg.client)}</span>`;
  if(pg.sensitivity){
    const cls = pg.sensitivity.indexOf("regulated")>=0 ? "reg" : (pg.sensitivity.indexOf("confidential")>=0 ? "conf":"");
    tags += `<span class="tag ${cls}">${esc(pg.sensitivity)}</span>`;
  }
  const body = `<main><h1>${esc(pg.title)}</h1><div class="meta">${tags}</div>${pg.html}</main>`;
  return shell(pg.title, navHtml(id), body);
}

function homeHtml(){
  const idx = DATA.pages["index"];
  const body = idx
    ? `<main>${idx.html}</main>`
    : `<main><h1>Velorixa Intelligence Layer</h1><p>Select a page.</p></main>`;
  return shell("Velorixa Intelligence Layer", navHtml("index"), body);
}

function shell(title, nav, main){
  return `<!doctype html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="robots" content="noindex,nofollow">
    <title>${esc(title)} &middot; VLX Intelligence Layer</title>
    <style>${STYLE}</style></head>
    <body><div class="banner">CLIENT-CONFIDENTIAL &middot; Velorixa (VLX) &middot; authorised access only</div>
    <div class="wrap">${nav}${main}</div></body></html>`;
}

function unauthorized(){
  return new Response("Authentication required", {
    status: 401,
    headers: {"WWW-Authenticate": 'Basic realm="VLX Intelligence Layer", charset="UTF-8"'},
  });
}

function checkAuth(request, env){
  // Fail CLOSED: if no credential is configured, serve nothing.
  if(!env.VIEWER_USER || !env.VIEWER_PASS) return "locked";
  const hdr = request.headers.get("Authorization") || "";
  if(!hdr.startsWith("Basic ")) return false;
  let decoded;
  try { decoded = atob(hdr.slice(6)); } catch(e){ return false; }
  const idx = decoded.indexOf(":");
  const u = decoded.slice(0, idx), p = decoded.slice(idx+1);
  return (u === env.VIEWER_USER && p === env.VIEWER_PASS);
}

export default {
  async fetch(request, env){
    const auth = checkAuth(request, env);
    if(auth === "locked"){
      return new Response("Viewer locked: no credentials configured. Set VIEWER_USER and VIEWER_PASS secrets.", {status: 503});
    }
    if(!auth) return unauthorized();

    const url = new URL(request.url);
    const path = decodeURIComponent(url.pathname);
    const headers = {"content-type":"text/html;charset=utf-8","cache-control":"no-store","x-robots-tag":"noindex"};
    if(path === "/" || path === "/index"){
      return new Response(homeHtml(), {headers});
    }
    if(path.startsWith("/p/")){
      const id = path.slice(3);
      const h = pageHtml(id);
      if(h) return new Response(h, {headers});
    }
    return new Response(shell("Not found", navHtml(""), "<main><h1>404</h1><p>No such page.</p></main>"), {status:404, headers});
  }
};
"""


if __name__ == "__main__":
    main()
