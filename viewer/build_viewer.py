#!/usr/bin/env python3
"""Node-free wiki viewer generator (Phase 5).

Reads the wiki markdown straight from this repo and renders a single
self-contained Cloudflare Worker (ES module) that serves a read-only,
auth-gated viewer. The landing view is an Obsidian-style association graph;
individual pages render with frontmatter tags and resolved WikiLinks.

No Node, no build step, no CDN: the force-directed graph is a small vanilla-JS
simulation embedded in the Worker, so nothing about the confidential wiki leaks
to a third-party script host.

Confidentiality: the wiki is client-confidential, so the generated Worker
enforces HTTP Basic Auth and fails CLOSED (503) when its credential binding is
absent. Nothing is served unauthenticated.

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

# Pages excluded from the association graph: pure infrastructure, not knowledge
# nodes. The index is kept but de-emphasised (small, no outbound edges) so it
# does not dominate the way a catalogue hub otherwise would.
GRAPH_EXCLUDE = {"log", "CLAUDE"}

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
CITE_RE = re.compile(r"\^?\[src:([^\]]+)\]")


def split_frontmatter(text):
    m = FM_RE.match(text)
    if not m:
        return {}, "", text
    return parse_fm(m.group(1)), m.group(1), text[m.end():]


def parse_fm(fm_raw):
    """Tiny frontmatter reader: scalars, plus the list keys we care about
    (`related:` of paths and `sources:`/`see_raw_for:` of `- id: <hash>`)."""
    fm = {"related": [], "source_ids": []}
    lines = fm_raw.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith(" ") and not line.startswith("-"):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val:
                fm[key] = val
                i += 1
                continue
            # block: collect indented children
            children = []
            j = i + 1
            while j < len(lines) and (lines[j].startswith(" ") or lines[j].startswith("\t")):
                children.append(lines[j])
                j += 1
            if key == "related":
                for c in children:
                    mm = re.match(r"\s*-\s*(.+?)\s*$", c)
                    if mm:
                        fm["related"].append(mm.group(1).strip())
            if key in ("sources", "see_raw_for"):
                for c in children:
                    mm = re.match(r"\s*-?\s*id:\s*([0-9a-f]+)\s*$", c)
                    if mm:
                        fm["source_ids"].append(mm.group(1).strip())
            i = j
            continue
        i += 1
    return fm


# ---- minimal markdown -> html (line based) -------------------------------

INLINE_CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
ITALIC_RE = re.compile(r"(?<![\*])\*([^*]+)\*(?![\*])")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")


def inline(text):
    placeholders = {}

    def stash(m):
        key = f"\x00{len(placeholders)}\x00"
        placeholders[key] = "<code>" + html.escape(m.group(1)) + "</code>"
        return key

    text = INLINE_CODE_RE.sub(stash, text)
    text = html.escape(text)
    text = CITE_RE.sub(lambda m: f'<sup class="cite" title="source {m.group(1)}">[src:{m.group(1)}]</sup>', text)
    text = WIKILINK_RE.sub(lambda m: f'<a class="wl" href="/p/{m.group(1).strip()}">{m.group(1).strip()}</a>', text)
    text = LINK_RE.sub(lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    text = BOLD_RE.sub(r"<strong>\1</strong>", text)
    text = ITALIC_RE.sub(r"<em>\1</em>", text)
    for k, v in placeholders.items():
        text = text.replace(k, v)
    return text


def md_to_html(body):
    lines = body.splitlines()
    out, i = [], 0
    in_code, code_buf, list_stack = False, [], []

    def close_lists():
        while list_stack:
            out.append(f"</{list_stack.pop()}>")

    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            if in_code:
                out.append("<pre><code>" + html.escape("\n".join(code_buf)) + "</code></pre>")
                code_buf, in_code = [], False
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
            lvl = len(h.group(1))
            out.append(f"<h{lvl}>{inline(h.group(2))}</h{lvl}>")
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
            out.append(f"<li>{inline((ul or ol).group(2))}</li>")
            i += 1
            continue
        if stripped.startswith(">"):
            close_lists()
            out.append(f"<blockquote>{inline(stripped[1:].strip())}</blockquote>")
            i += 1
            continue
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
    if nid in ("index", "log"):
        return nid
    top = nid.split("/")[0]
    return top if top in dict(SECTION_ORDER) else "other"


def type_of(nid):
    sec = section_of(nid)
    singular = {"sources": "source", "synthesis": "synthesis", "skills": "skill",
                "entities": "entity", "concepts": "concept", "projects": "project",
                "decisions": "decision", "index": "index", "schema": "schema"}
    return singular.get(sec, sec)


def collect():
    """Return (pages, raw) where pages maps node id -> page dict, and raw maps
    node id -> {related, source_ids, wikilinks, citations}."""
    pages, raw = {}, {}
    for p in sorted(WIKI.rglob("*.md")):
        rel = p.relative_to(WIKI)
        if rel.parts[0] == "_templates":
            continue
        nid = node_id(p)
        fm, _, body = split_frontmatter(p.read_text())
        title = fm.get("title") or nid.split("/")[-1].replace("-", " ")
        pages[nid] = {
            "id": nid, "title": title,
            "type": fm.get("type", type_of(nid)),
            "sensitivity": fm.get("sensitivity", ""),
            "client": fm.get("client", ""),
            "html": md_to_html(body),
        }
        raw[nid] = {
            "related": fm.get("related", []),
            "source_ids": fm.get("source_ids", []),
            "wikilinks": [m.group(1).strip() for m in WIKILINK_RE.finditer(body)],
            "citations": [m.group(1) for m in CITE_RE.finditer(body)],
        }
    return pages, raw


def build_graph(pages, raw):
    """Build the association graph. Edges come from inline WikiLinks, the
    `related:` frontmatter, and citations (resolved to the source page that owns
    the cited id). The index is kept as a node but contributes no edges, so it
    stays peripheral instead of dominating as a catalogue hub."""
    # map source id (full + short_ref) -> owning page node id
    src_to_page = {}
    for nid, r in raw.items():
        for sid in r["source_ids"]:
            src_to_page[sid] = nid
            src_to_page[sid[:8]] = nid

    graph_pages = {nid for nid in pages if nid not in GRAPH_EXCLUDE}
    nodes = {}          # id -> node dict
    resolved = set(pages.keys())

    def ensure(nid, unresolved=False):
        if nid not in nodes:
            nodes[nid] = {
                "id": nid,
                "title": pages[nid]["title"] if nid in pages else nid.split("/")[-1].replace("-", " "),
                "type": pages[nid]["type"] if nid in pages else type_of(nid),
                "unresolved": unresolved,
                "deg": 0,
            }
        return nodes[nid]

    for nid in graph_pages:
        ensure(nid)

    edges = set()

    def add_edge(a, b):
        if a == b:
            return
        edges.add(tuple(sorted((a, b))))

    for nid in graph_pages:
        r = raw[nid]
        # index contributes no outbound edges (de-emphasised)
        if nid == "index":
            continue
        targets = set(r["wikilinks"]) | set(r["related"])
        for t in targets:
            t = t.strip()
            if not t:
                continue
            ensure(t, unresolved=(t not in resolved))
            add_edge(nid, t)
        for c in r["citations"]:
            owner = src_to_page.get(c) or src_to_page.get(c[:8])
            if owner and owner in nodes:
                add_edge(nid, owner)

    # skill sub-pages (e.g. layout_catalogue) are not graph nodes
    for nid in list(nodes):
        if nid.startswith("skills/") and not nid.endswith("/SKILL") and nid not in resolved:
            pass  # keep unresolved targets; only drop real sub-pages
    drop = {nid for nid in nodes
            if nid.startswith("skills/") and not nid.endswith("/SKILL") and nid in resolved}
    for nid in drop:
        del nodes[nid]
    edges = {(a, b) for (a, b) in edges if a not in drop and b not in drop}

    for (a, b) in edges:
        nodes[a]["deg"] += 1
        nodes[b]["deg"] += 1

    node_list = list(nodes.values())
    idx = {n["id"]: i for i, n in enumerate(node_list)}
    edge_list = [{"s": idx[a], "t": idx[b]} for (a, b) in sorted(edges)]
    return {"nodes": node_list, "edges": edge_list}


def build_nav(pages):
    nav = []
    for key, label in SECTION_ORDER:
        entries = []
        for nid, pg in pages.items():
            if section_of(nid) != key:
                continue
            if key == "skills" and not nid.endswith("/SKILL"):
                continue
            entries.append({"id": nid, "title": pg["title"]})
        if entries:
            nav.append({"label": label, "entries": sorted(entries, key=lambda e: e["id"])})
    return nav


def main():
    pages, raw = collect()
    nav = build_nav(pages)
    graph = build_graph(pages, raw)
    data = {"pages": pages, "nav": nav, "graph": graph}
    # Safe embedding inside a <script>: neutralise tag/breakout sequences.
    payload = (json.dumps(data, ensure_ascii=False)
               .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
               .replace(" ", "\\u2028").replace(" ", "\\u2029"))
    OUT.write_text(WORKER_TEMPLATE.replace("__DATA__", payload))
    n_conf = sum(1 for p in pages.values() if "confidential" in p["sensitivity"] or "regulated" in p["sensitivity"])
    n_unres = sum(1 for n in graph["nodes"] if n["unresolved"])
    print(f"built {OUT.relative_to(REPO)}: {len(pages)} page(s), "
          f"graph {len(graph['nodes'])} node(s) ({n_unres} unresolved) / {len(graph['edges'])} edge(s), "
          f"{n_conf} confidential/regulated page(s), public viewer")


WORKER_TEMPLATE = r"""// Velorixa Intelligence Layer viewer (Phase 5) -- generated by viewer/build_viewer.py
// Read-only intelligence layer viewer. Authentication is disabled by site owner request.
const DATA = __DATA__;

const TYPE_COLORS = {
  entity:"#31dcff", concept:"#b2ef68", source:"#ff558f", project:"#ffc8b0",
  synthesis:"#a92473", decision:"#ffb020", skill:"#8b7cf6", index:"#64748b",
  schema:"#64748b", other:"#c7ccd4"
};

const STYLE = `
  :root{color-scheme:dark;--ink:#f4f5f7;--mut:#9da3ad;--line:#2b313c;--accent:#31dcff;--warn:#ffb020;--bg:#161618;--edge:rgba(180,186,196,.18);--edge-hot:rgba(255,255,255,.52)}
  *{box-sizing:border-box}
  html,body{width:100%;min-height:100%;margin:0;font:15px/1.6 -apple-system,Inter,Segoe UI,sans-serif;color:var(--ink);background:var(--bg)}
  body.graph-view{height:100%;overflow:hidden;background:radial-gradient(circle at 50% 46%,rgba(80,92,105,.12),transparent 38%),var(--bg);font:13px/1.4 Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
  .banner{background:#0f1117;color:#cbd5e1;border-bottom:1px solid #242936;padding:6px 16px;font-size:12px;letter-spacing:.02em;text-align:center}
  .wrap{display:flex;min-height:calc(100vh - 28px);background:#fafafa;color:#1a1a2e}
  nav{width:280px;border-right:1px solid #e5e7eb;padding:18px 16px;background:#fff;overflow-y:auto;height:calc(100vh - 28px);position:sticky;top:0}
  nav h1{font-size:15px;margin:0 0 4px}
  nav .sub{color:#6b7280;font-size:12px;margin-bottom:14px}
  nav .navtop{display:flex;gap:8px;margin-bottom:8px}
  nav .navtop a{flex:1;text-align:center;border:1px solid #e5e7eb;border-radius:6px;padding:5px;font-size:12px;text-decoration:none;color:#1a1a2e}
  nav .navtop a.on{background:#ecfdf5;border-color:#99f6e4;color:#0f766e;font-weight:600}
  nav .sec{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#6b7280;margin:16px 0 6px}
  nav a.pg{display:block;color:#1a1a2e;text-decoration:none;padding:3px 6px;border-radius:5px;font-size:13px}
  nav a.pg:hover{background:#f1f5f9}
  nav a.pg.active{background:#ecfdf5;color:#0f766e;font-weight:600}
  main{flex:1;padding:32px 48px;max-width:880px}
  main h1{margin-top:0}
  .meta{display:flex;gap:8px;flex-wrap:wrap;margin:0 0 20px}
  .tag{font-size:11px;padding:2px 8px;border-radius:999px;background:#f1f5f9;color:#6b7280}
  .tag.conf{background:#fef3c7;color:#b45309}
  .tag.reg{background:#fee2e2;color:#991b1b}
  sup.cite{color:#0f766e;font-weight:600;cursor:help}
  a.wl{color:#0f766e;text-decoration:none;border-bottom:1px dotted #0f766e}
  pre{background:#0f172a;color:#e2e8f0;padding:14px;border-radius:8px;overflow:auto;font-size:13px}
  code{background:#f1f5f9;padding:1px 5px;border-radius:4px;font-size:13px}
  pre code{background:none;padding:0}
  blockquote{border-left:3px solid #e5e7eb;margin:0;padding:4px 16px;color:#6b7280}
  hr{border:none;border-top:1px solid #e5e7eb;margin:24px 0}
  /* graph */
  .graphmain{position:fixed;inset:0;background:radial-gradient(circle at 50% 46%,rgba(80,92,105,.12),transparent 38%),var(--bg);overflow:hidden}
  #graph{display:block;width:100vw;height:100vh;cursor:grab}
  #graph:active{cursor:grabbing}
  #graphHud{position:fixed;left:16px;bottom:14px;max-width:min(460px,calc(100vw - 32px));color:var(--mut);pointer-events:none;text-shadow:0 1px 8px rgba(0,0,0,.74);user-select:none}
  .hud-title{color:var(--ink);font-size:12px;font-weight:780;letter-spacing:0}
  .hud-meta{margin-top:3px;font-size:11px}
`;

function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");}

function navHtml(active, view){
  let h = `<h1>Velorixa Intelligence Layer</h1><div class="sub">Layer 1 wiki &middot; read-only</div>`;
  h += `<div class="navtop"><a class="${view==='graph'?'on':''}" href="/">Graph</a>`+
       `<a class="${active==='index'?'on':''}" href="/p/index">Index</a></div>`;
  for(const sec of DATA.nav){
    if(sec.label==='Index') continue;
    h += `<div class="sec">${esc(sec.label)}</div>`;
    for(const e of sec.entries){
      h += `<a class="pg ${e.id===active?'active':''}" href="/p/${encodeURI(e.id)}">${esc(e.title)}</a>`;
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
    const cls = pg.sensitivity.indexOf("regulated")>=0?"reg":(pg.sensitivity.indexOf("confidential")>=0?"conf":"");
    tags += `<span class="tag ${cls}">${esc(pg.sensitivity)}</span>`;
  }
  const main = `<main><h1>${esc(pg.title)}</h1><div class="meta">${tags}</div>${pg.html}</main>`;
  return shell(pg.title, navHtml(id,'page'), main);
}

function graphPage(){
  const main = `<div class="graphmain">
    <canvas id="graph" aria-label="Intelligence Layer association graph"></canvas>
    <div id="graphHud" aria-live="polite"></div>
  </div>`;
  // Inject the graph data into the browser (DATA only exists server-side).
  const gjson = JSON.stringify(DATA.graph).split("<").join("\\u003c");
  const script = "const GRAPH=" + gjson + ";\n" + GRAPH_JS;
  return `<!doctype html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="robots" content="noindex,nofollow">
    <title>Graph &middot; VLX Intelligence Layer</title>
    <style>${STYLE}</style></head>
    <body class="graph-view">${main}<script>${script}</script></body></html>`;
}

function shell(title, nav, main, script){
  return `<!doctype html><html><head><meta charset="utf-8">
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <meta name="robots" content="noindex,nofollow">
    <title>${esc(title)} &middot; VLX Intelligence Layer</title>
    <style>${STYLE}</style></head>
    <body><div class="banner">CLIENT-CONFIDENTIAL &middot; Velorixa (VLX) &middot; authorised access only</div>
    <div class="wrap">${nav}${main}</div>${script?('<script>'+script+'</script>'):''}</body></html>`;
}

const TYPE_COLORS_RUNTIME = TYPE_COLORS;

const GRAPH_JS = `
const canvas=document.getElementById("graph");
const ctx=canvas.getContext("2d");
const hud=document.getElementById("graphHud");
const COLORS=${JSON.stringify(TYPE_COLORS_RUNTIME)};
const LABELS={entity:"entity",concept:"concept",source:"source",project:"project",synthesis:"synthesis",decision:"decision",skill:"skill",index:"index",schema:"schema",other:"page"};
let width=0,height=0,dpr=1;
let nodes=GRAPH.nodes.map(n=>Object.assign({},n,{vx:0,vy:0}));
let edges=GRAPH.edges.map(e=>Object.assign({},e));
let adjacency=new Map(nodes.map((_,i)=>[i,new Set()]));
let hovered=null,selected=null,dragging=null;
let pointer={x:0,y:0,down:false,moved:false};
let camera={x:0,y:0,scale:1};

for(const edge of edges){
  adjacency.get(edge.s)?.add(edge.t);
  adjacency.get(edge.t)?.add(edge.s);
}

function isIndexNode(node){return node.id==="index";}
function nodeRadius(node){return isIndexNode(node)?4:5+Math.min(9,Math.sqrt((node.deg||0)+1)*1.9);}
function shortTitle(node){
  const title=node.title||node.id.split("/").pop();
  return title.length>36?title.slice(0,33)+"...":title;
}

function resize(){
  dpr=Math.min(window.devicePixelRatio||1,2);
  width=window.innerWidth;
  height=window.innerHeight;
  canvas.width=Math.round(width*dpr);
  canvas.height=Math.round(height*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);
  camera.x=width/2;
  camera.y=height/2;
}

function initialisePositions(){
  const types=[...new Set(nodes.map(n=>n.type||"other"))].sort();
  const typeIndex=new Map(types.map((type,index)=>[type,index]));
  const radiusBase=Math.min(width,height)*0.28;
  nodes=nodes.map((node,index)=>{
    const group=typeIndex.get(node.type||"other")||0;
    const angle=(index/Math.max(1,nodes.length))*Math.PI*2+group*0.52;
    const radius=radiusBase+(group%5)*36;
    return Object.assign(node,{
      x:Math.cos(angle)*radius+(Math.random()-0.5)*80,
      y:Math.sin(angle)*radius+(Math.random()-0.5)*80,
      vx:0,
      vy:0,
      r:nodeRadius(node)
    });
  });
}

function screenToWorld(x,y){
  return {x:(x-camera.x)/camera.scale,y:(y-camera.y)/camera.scale};
}

function relatedSet(){
  const root=hovered||selected;
  if(root===null)return new Set();
  return new Set([root,...(adjacency.get(root)||[])]);
}

function simulate(){
  for(let i=0;i<nodes.length;i+=1){
    for(let j=i+1;j<nodes.length;j+=1){
      const a=nodes[i],b=nodes[j];
      const repulsionScale=isIndexNode(a)||isIndexNode(b)?0.38:1;
      const dx=b.x-a.x||0.01;
      const dy=b.y-a.y||0.01;
      const distanceSq=Math.max(100,dx*dx+dy*dy);
      const force=(1700*repulsionScale)/distanceSq;
      const distance=Math.sqrt(distanceSq);
      const fx=(dx/distance)*force;
      const fy=(dy/distance)*force;
      a.vx-=fx;a.vy-=fy;b.vx+=fx;b.vy+=fy;
    }
  }

  for(const edge of edges){
    const a=nodes[edge.s],b=nodes[edge.t];
    if(!a||!b)continue;
    const dx=b.x-a.x;
    const dy=b.y-a.y;
    const distance=Math.max(1,Math.sqrt(dx*dx+dy*dy));
    const force=(distance-105)*0.007;
    const fx=(dx/distance)*force;
    const fy=(dy/distance)*force;
    a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;
  }

  for(const node of nodes){
    if(node===dragging)continue;
    node.vx+=-node.x*0.0007;
    node.vy+=-node.y*0.0007;
    node.x+=node.vx;
    node.y+=node.vy;
    node.vx*=0.86;
    node.vy*=0.86;
  }
}

function draw(){
  simulate();
  ctx.clearRect(0,0,width,height);
  ctx.save();
  ctx.translate(camera.x,camera.y);
  ctx.scale(camera.scale,camera.scale);

  const hot=relatedSet();
  const hotActive=hot.size>0;
  const t=performance.now()/1000;

  ctx.lineCap="round";
  for(const edge of edges){
    const a=nodes[edge.s],b=nodes[edge.t];
    if(!a||!b)continue;
    const active=hot.has(edge.s)&&hot.has(edge.t);
    ctx.strokeStyle=active?"rgba(255,255,255,0.55)":hotActive?"rgba(170,176,186,0.055)":"rgba(170,176,186,0.18)";
    ctx.lineWidth=active?1.4:0.8;
    ctx.beginPath();
    ctx.moveTo(a.x,a.y);
    ctx.lineTo(b.x,b.y);
    ctx.stroke();
  }

  for(let index=0;index<nodes.length;index+=1){
    const node=nodes[index];
    const degree=adjacency.get(index)?.size||0;
    const active=hot.has(index);
    const chosen=selected===index;
    const color=COLORS[node.type]||COLORS.other;
    const pulse=1+Math.sin(t*2.2+node.x*0.01)*0.08;
    const radius=(node.r+(chosen?5:active?2.5:0))*pulse;
    const isIndex=isIndexNode(node);
    ctx.globalAlpha=isIndex?(hotActive&&!active?0.12:0.26):hotActive&&!active?0.28:1;
    ctx.fillStyle=node.unresolved?"#161618":color;
    ctx.beginPath();
    ctx.arc(node.x,node.y,radius,0,Math.PI*2);
    ctx.fill();
    ctx.strokeStyle=chosen?"#ffffff":active?"rgba(255,255,255,0.86)":node.unresolved?color:"rgba(255,255,255,0.38)";
    ctx.lineWidth=chosen?3:active?1.8:1;
    ctx.stroke();

    const important=degree>=6||(node.type!=="source"&&degree>=4)||node.type==="project"||node.type==="synthesis";
    const showLabel=!isIndex&&(chosen||active||(!hotActive&&important));
    if(showLabel){
      ctx.font=(chosen?"700 13px":"500 11px")+" Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif";
      ctx.fillStyle=chosen||active?"#f7f8fb":"rgba(210,214,221,0.68)";
      ctx.shadowColor="#161618";
      ctx.shadowBlur=8;
      ctx.fillText(shortTitle(node),node.x+radius+6,node.y+4);
      ctx.shadowBlur=0;
    }
  }
  ctx.globalAlpha=1;
  ctx.restore();

  const focus=hovered!==null?hovered:selected;
  const node=focus!==null?nodes[focus]:null;
  hud.innerHTML=node
    ? "<div class=\\"hud-title\\">"+escapeHtml(node.title||node.id)+"</div><div class=\\"hud-meta\\">"+escapeHtml(LABELS[node.type]||node.type||"page")+" · "+(adjacency.get(focus)?.size||0)+" associations</div>"
    : "<div class=\\"hud-title\\">Intelligence Layer Graph</div><div class=\\"hud-meta\\">"+nodes.length+" nodes · "+edges.length+" associations · live wiki sync</div>";

  requestAnimationFrame(draw);
}

function escapeHtml(value){
  return String(value).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
}

function nearestNode(world){
  let best=null;
  let bestDistance=Infinity;
  for(let i=0;i<nodes.length;i+=1){
    const node=nodes[i];
    const dx=node.x-world.x;
    const dy=node.y-world.y;
    const distance=Math.sqrt(dx*dx+dy*dy);
    if(distance<Math.max(18,node.r+10)&&distance<bestDistance){
      best=i;
      bestDistance=distance;
    }
  }
  return best;
}

function updateHover(event){
  const rect=canvas.getBoundingClientRect();
  pointer.x=event.clientX-rect.left;
  pointer.y=event.clientY-rect.top;
  if(dragging)return;
  hovered=nearestNode(screenToWorld(pointer.x,pointer.y));
}

canvas.addEventListener("pointermove",event=>{
  const previous={x:pointer.x,y:pointer.y};
  updateHover(event);
  if(!pointer.down)return;
  pointer.moved=true;
  const dx=pointer.x-previous.x;
  const dy=pointer.y-previous.y;
  if(dragging){
    const world=screenToWorld(pointer.x,pointer.y);
    dragging.x=world.x;
    dragging.y=world.y;
    dragging.vx=0;
    dragging.vy=0;
  }else{
    camera.x+=dx;
    camera.y+=dy;
  }
});

canvas.addEventListener("pointerdown",event=>{
  updateHover(event);
  pointer.down=true;
  pointer.moved=false;
  dragging=hovered!==null?nodes[hovered]:null;
  canvas.setPointerCapture(event.pointerId);
});

canvas.addEventListener("pointerup",event=>{
  updateHover(event);
  if(!pointer.moved&&hovered!==null){
    selected=hovered;
    const node=nodes[selected];
    if(node&&!node.unresolved)location.href="/p/"+encodeURI(node.id);
  }
  pointer.down=false;
  dragging=null;
  canvas.releasePointerCapture(event.pointerId);
});

canvas.addEventListener("pointerleave",()=>{hovered=null;});

canvas.addEventListener("wheel",event=>{
  event.preventDefault();
  const rect=canvas.getBoundingClientRect();
  const before=screenToWorld(event.clientX-rect.left,event.clientY-rect.top);
  const factor=Math.exp(-event.deltaY*0.001);
  camera.scale=Math.min(2.4,Math.max(0.42,camera.scale*factor));
  const after=screenToWorld(event.clientX-rect.left,event.clientY-rect.top);
  camera.x+=(after.x-before.x)*camera.scale;
  camera.y+=(after.y-before.y)*camera.scale;
},{passive:false});

window.addEventListener("resize",resize);
resize();
initialisePositions();
requestAnimationFrame(draw);
`;

function unauthorized(){
  return new Response("Authentication disabled", {status:200});
}
function checkAuth(request,env){
  return true;
}

export default {
  async fetch(request, env){
    const auth=checkAuth(request,env);
    if(!auth) return unauthorized();
    const url=new URL(request.url);
    const path=decodeURIComponent(url.pathname);
    const headers={"content-type":"text/html;charset=utf-8","cache-control":"no-store","x-robots-tag":"noindex"};
    if(path==="/"||path==="/graph") return new Response(graphPage(),{headers});
    if(path.startsWith("/p/")){const h=pageHtml(path.slice(3)); if(h) return new Response(h,{headers});}
    return new Response(shell("Not found",navHtml('','page'),"<main><h1>404</h1><p>No such page.</p></main>"),{status:404,headers});
  }
};
"""


if __name__ == "__main__":
    main()
