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
          f"{n_conf} confidential/regulated page(s), Basic-Auth gated")


WORKER_TEMPLATE = r"""// Velorixa Intelligence Layer viewer (Phase 5) -- generated by viewer/build_viewer.py
// Read-only, auth-gated. Serves client-confidential content; fails CLOSED.
const DATA = __DATA__;

const TYPE_COLORS = {
  source:"#0ea5e9", synthesis:"#8b5cf6", skill:"#10b981", entity:"#f59e0b",
  project:"#ef4444", concept:"#ec4899", decision:"#14b8a6", index:"#94a3b8",
  schema:"#64748b", other:"#94a3b8"
};

const STYLE = `
  :root{--ink:#1a1a2e;--mut:#6b7280;--line:#e5e7eb;--accent:#0f766e;--warn:#b45309;--bg:#0b1020}
  *{box-sizing:border-box}
  body{margin:0;font:15px/1.6 -apple-system,Inter,Segoe UI,sans-serif;color:#1a1a2e;background:#fafafa}
  .banner{background:#7f1d1d;color:#fff;padding:6px 16px;font-size:12px;letter-spacing:.02em;text-align:center}
  .wrap{display:flex;min-height:calc(100vh - 28px)}
  nav{width:280px;border-right:1px solid var(--line);padding:18px 16px;background:#fff;overflow-y:auto;height:calc(100vh - 28px);position:sticky;top:0}
  nav h1{font-size:15px;margin:0 0 4px}
  nav .sub{color:var(--mut);font-size:12px;margin-bottom:14px}
  nav .navtop{display:flex;gap:8px;margin-bottom:8px}
  nav .navtop a{flex:1;text-align:center;border:1px solid var(--line);border-radius:6px;padding:5px;font-size:12px;text-decoration:none;color:var(--ink)}
  nav .navtop a.on{background:#ecfdf5;border-color:#99f6e4;color:var(--accent);font-weight:600}
  nav .sec{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:16px 0 6px}
  nav a.pg{display:block;color:var(--ink);text-decoration:none;padding:3px 6px;border-radius:5px;font-size:13px}
  nav a.pg:hover{background:#f1f5f9}
  nav a.pg.active{background:#ecfdf5;color:var(--accent);font-weight:600}
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
  /* graph */
  .graphmain{flex:1;position:relative;background:radial-gradient(circle at 50% 40%,#131a33,#0b1020)}
  #graph{width:100%;height:100%;display:block;cursor:grab}
  #graph.grabbing{cursor:grabbing}
  .glabel{font:11px -apple-system,Inter,sans-serif;fill:#cbd5e1;pointer-events:none;paint-order:stroke;stroke:#0b1020;stroke-width:3px}
  .gnode{cursor:pointer}
  .gedge{stroke:#475569;stroke-opacity:.5}
  .legend{position:absolute;left:14px;bottom:14px;background:rgba(11,16,32,.72);border:1px solid #1e293b;border-radius:8px;padding:10px 12px;color:#cbd5e1;font-size:12px}
  .legend .row{display:flex;align-items:center;gap:7px;margin:3px 0}
  .legend .dot{width:9px;height:9px;border-radius:50%}
  .ghint{position:absolute;right:14px;top:14px;background:rgba(11,16,32,.72);border:1px solid #1e293b;border-radius:8px;padding:8px 11px;color:#94a3b8;font-size:12px;max-width:230px}
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
    <svg id="graph"></svg>
    <div class="ghint">Drag nodes to pull them around &middot; scroll to zoom &middot; click a node to open it. Hollow nodes are referenced but not yet written.</div>
    <div class="legend" id="legend"></div>
  </div>`;
  // Inject the graph data into the browser (DATA only exists server-side).
  const gjson = JSON.stringify(DATA.graph).split("<").join("\\u003c");
  const script = "const GRAPH=" + gjson + ";\n" + GRAPH_JS;
  return shell("Graph", navHtml('','graph'), main, script);
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
const NS="http://www.w3.org/2000/svg";
const svg=document.getElementById("graph");
const COLORS=${JSON.stringify(TYPE_COLORS_RUNTIME)};
const nodes=GRAPH.nodes.map(n=>Object.assign({},n));
const edges=GRAPH.edges.map(e=>Object.assign({},e));
let W=svg.clientWidth||900, H=svg.clientHeight||600;
const cx=()=>W/2, cy=()=>H/2;

// initial positions in a ring around centre
nodes.forEach((n,i)=>{const a=i/nodes.length*Math.PI*2;n.x=cx()+Math.cos(a)*Math.min(W,H)*0.28;n.y=cy()+Math.sin(a)*Math.min(W,H)*0.28;n.vx=0;n.vy=0;});

const radius=n=> (n.id==="index"?5:6) + Math.sqrt(n.deg)*4;
const charge=n=> n.id==="index"? -250 : -(800 + n.deg*220);

// view transform (zoom/pan)
let tx=0, ty=0, scale=1;
const root=document.createElementNS(NS,"g");
svg.appendChild(root);
const edgeG=document.createElementNS(NS,"g"); root.appendChild(edgeG);
const nodeG=document.createElementNS(NS,"g"); root.appendChild(nodeG);

// adjacency for hover highlight
const adj={}; nodes.forEach((n,i)=>adj[i]=new Set());
edges.forEach(e=>{adj[e.s].add(e.t);adj[e.t].add(e.s);});

const edgeEls=edges.map(e=>{const l=document.createElementNS(NS,"line");l.setAttribute("class","gedge");l.setAttribute("stroke-width",1.1);edgeG.appendChild(l);return l;});
const nodeEls=nodes.map((n,i)=>{
  const g=document.createElementNS(NS,"g");g.setAttribute("class","gnode");
  const c=document.createElementNS(NS,"circle");
  const col=COLORS[n.type]||COLORS.other;
  c.setAttribute("r",radius(n));
  if(n.unresolved){c.setAttribute("fill","#0b1020");c.setAttribute("stroke",col);c.setAttribute("stroke-dasharray","2 2");c.setAttribute("stroke-width",1.5);}
  else{c.setAttribute("fill",col);c.setAttribute("stroke","#0b1020");c.setAttribute("stroke-width",1.5);}
  if(n.id==="index"){c.setAttribute("opacity",.65);}
  const t=document.createElementNS(NS,"text");t.setAttribute("class","glabel");t.setAttribute("text-anchor","middle");t.textContent=n.title;
  g.appendChild(c);g.appendChild(t);nodeG.appendChild(g);
  g._c=c;g._t=t;g._i=i;return g;
});

function applyTransform(){root.setAttribute("transform",\`translate(\${tx},\${ty}) scale(\${scale})\`);}

function render(){
  edges.forEach((e,k)=>{const a=nodes[e.s],b=nodes[e.t];const l=edgeEls[k];l.setAttribute("x1",a.x);l.setAttribute("y1",a.y);l.setAttribute("x2",b.x);l.setAttribute("y2",b.y);});
  nodes.forEach((n,i)=>{const g=nodeEls[i];g._c.setAttribute("cx",n.x);g._c.setAttribute("cy",n.y);g._t.setAttribute("x",n.x);g._t.setAttribute("y",n.y - radius(n) - 5);});
}

// force simulation
let alpha=1;
function step(){
  if(alpha>0.005){
    for(let i=0;i<nodes.length;i++){
      const a=nodes[i];
      for(let j=i+1;j<nodes.length;j++){
        const b=nodes[j];
        let dx=a.x-b.x, dy=a.y-b.y; let d2=dx*dx+dy*dy; if(d2<0.01)d2=0.01; const d=Math.sqrt(d2);
        const f=(charge(a)+charge(b))/2 / d2 * alpha; // repulsion (negative charge => push apart)
        const fx=dx/d*f, fy=dy/d*f;
        a.vx-=fx;a.vy-=fy;b.vx+=fx;b.vy+=fy;
      }
      // centre gravity
      a.vx+=(cx()-a.x)*0.015*alpha;
      a.vy+=(cy()-a.y)*0.015*alpha;
    }
    // spring attraction along edges
    edges.forEach(e=>{
      const a=nodes[e.s],b=nodes[e.t];
      let dx=b.x-a.x, dy=b.y-a.y; const d=Math.sqrt(dx*dx+dy*dy)||0.01;
      const rest=90; const k=0.04*alpha; const f=(d-rest)*k;
      const fx=dx/d*f, fy=dy/d*f;
      a.vx+=fx;a.vy+=fy;b.vx-=fx;b.vy-=fy;
    });
    nodes.forEach(n=>{
      if(n.fixed){n.vx=0;n.vy=0;return;}
      n.x+=n.vx*0.85;n.y+=n.vy*0.85;n.vx*=0.82;n.vy*=0.82;
    });
    alpha*=0.985;
  }
  render();
  requestAnimationFrame(step);
}

// interactions
function clearHi(){nodeEls.forEach(g=>{g._c.style.opacity=1;g._t.style.opacity=1;});edgeEls.forEach(l=>{l.style.opacity="";l.setAttribute("stroke","#475569");});}
function highlight(i){
  nodeEls.forEach((g,k)=>{const on=(k===i||adj[i].has(k));g._c.style.opacity=on?1:.15;g._t.style.opacity=on?1:.1;});
  edges.forEach((e,k)=>{const on=(e.s===i||e.t===i);edgeEls[k].style.opacity=on?1:.06;edgeEls[k].setAttribute("stroke",on?"#22d3ee":"#475569");});
}

let drag=null, moved=false, panning=false, panStart=null;
function ptr(evt){const r=svg.getBoundingClientRect();return {x:(evt.clientX-r.left-tx)/scale, y:(evt.clientY-r.top-ty)/scale};}

nodeEls.forEach((g,i)=>{
  g.addEventListener("pointerenter",()=>{if(!drag)highlight(i);});
  g.addEventListener("pointerleave",()=>{if(!drag)clearHi();});
  g.addEventListener("pointerdown",ev=>{ev.stopPropagation();drag={i,};moved=false;const p=ptr(ev);nodes[i].fixed=true;g.setPointerCapture(ev.pointerId);drag.pid=ev.pointerId;alpha=Math.max(alpha,0.4);highlight(i);});
  g.addEventListener("pointermove",ev=>{if(!drag||drag.i!==i)return;const p=ptr(ev);nodes[i].x=p.x;nodes[i].y=p.y;moved=true;});
  g.addEventListener("pointerup",ev=>{if(!drag||drag.i!==i)return;nodes[i].fixed=false;const n=nodes[i];drag=null;clearHi();if(!moved){if(!n.unresolved){location.href="/p/"+encodeURI(n.id);}}});
});

// background pan + zoom
svg.addEventListener("pointerdown",ev=>{panning=true;panStart={x:ev.clientX-tx,y:ev.clientY-ty};svg.classList.add("grabbing");});
svg.addEventListener("pointermove",ev=>{if(!panning)return;tx=ev.clientX-panStart.x;ty=ev.clientY-panStart.y;applyTransform();});
window.addEventListener("pointerup",()=>{panning=false;svg.classList.remove("grabbing");});
svg.addEventListener("wheel",ev=>{ev.preventDefault();const r=svg.getBoundingClientRect();const mx=ev.clientX-r.left,my=ev.clientY-r.top;const f=ev.deltaY<0?1.1:0.9;const ns=Math.min(4,Math.max(0.25,scale*f));tx=mx-(mx-tx)*(ns/scale);ty=my-(my-ty)*(ns/scale);scale=ns;applyTransform();},{passive:false});

function resize(){W=svg.clientWidth;H=svg.clientHeight;}
window.addEventListener("resize",resize);

// legend
const present=[...new Set(nodes.map(n=>n.type))];
document.getElementById("legend").innerHTML = present.map(t=>\`<div class="row"><span class="dot" style="background:\${COLORS[t]||COLORS.other}"></span>\${t}</div>\`).join("") + '<div class="row"><span class="dot" style="background:#0b1020;border:1.5px dashed #94a3b8"></span>unresolved</div>';

resize();applyTransform();step();
`;

function unauthorized(){
  return new Response("Authentication required",{status:401,headers:{"WWW-Authenticate":'Basic realm="VLX Intelligence Layer", charset="UTF-8"'}});
}
function checkAuth(request,env){
  if(!env.VIEWER_USER||!env.VIEWER_PASS) return "locked";
  const hdr=request.headers.get("Authorization")||"";
  if(!hdr.startsWith("Basic ")) return false;
  let decoded; try{decoded=atob(hdr.slice(6));}catch(e){return false;}
  const idx=decoded.indexOf(":"); const u=decoded.slice(0,idx), p=decoded.slice(idx+1);
  return (u===env.VIEWER_USER && p===env.VIEWER_PASS);
}

export default {
  async fetch(request, env){
    const auth=checkAuth(request,env);
    if(auth==="locked") return new Response("Viewer locked: no credentials configured. Set VIEWER_USER and VIEWER_PASS secrets.",{status:503});
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
