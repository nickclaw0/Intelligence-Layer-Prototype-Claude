#!/usr/bin/env python3
"""
generate-avalere-docx build engine (template-as-base).

Starts from the pinned Avalere Word template, clears its demo body content while
keeping the section properties (so the header, footers, and the embedded logo are
preserved), and adds paragraphs using the template's own named styles. The brand
comes from the template's styles and theme, never from ad-hoc formatting.

Pure standard library (zipfile + regex over word/document.xml): the runtime here
is Python 3.9 with no third-party packages and no network, and a teammate cloning
the repo should not have to install anything. We open the .docx as a zip, keep
every part byte-for-byte except word/document.xml, and inside that part we replace
only the body paragraphs, leaving the trailing <w:sectPr> (which wires the
header/footers and page setup) and every other part untouched. That is what keeps
header1, footer1, footer2, and the logo media alive in the output.

Usage:
    python3 build_doc.py <spec.json> [--template <path>] [--out <path>]
    python3 build_doc.py list-styles [<template>]

Spec JSON shape:
{
  "output": "doc.docx",
  "blocks": [
    {"style": "Title",       "text": "Velorixa"},
    {"style": "Subtitle",    "text": "Brand strategy kickoff recap"},
    {"style": "Heading 1",   "text": "Brand ambition"},
    {"style": "Normal",      "text": "The core pressure is clarity.", "citations": ["623851f2"]},
    {"style": "List Bullet",  "text": "Top-level point", "citations": ["623851f2"]},
    {"style": "List Bullet 2", "text": "Nested point"},          # nesting via List Bullet 2..5
    {"type": "table", "style": "1 by 1 Grey with Orange Rule",   # branded table
     "header": true,
     "rows": [["Phase", "Output"], ["Foundation", "Positioning"]]}
  ],
  "clear_template_body": true
}

A block is a styled paragraph by default. Set "type": "table" for a branded table
(rows = list of row-lists; "header": true bolds the first row). Nest bullets/numbers
with the List Bullet 2..5 / List Number 2..5 styles. Style names are matched dash-
and case-insensitively against the template's own named styles (use list-styles to
print them). Citations render inline as [src:id].
"""
import sys, os, json, argparse, zipfile, re, tempfile, urllib.request
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))


def _find_template(filename):
    """Locate the pinned template in either the repo layout or a self-contained
    skill bundle. Repo: ../_assets/<file>. Bundle (e.g. installed on Claude.ai):
    the template is shipped inside the skill folder under assets/ or alongside it."""
    candidates = [
        os.path.join(HERE, "assets", filename),                          # bundled skill layout
        os.path.join(HERE, filename),                                    # co-located
        os.path.normpath(os.path.join(HERE, "..", "_assets", filename)), # repo layout
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[-1]  # repo default; a missing-file error surfaces clearly at open


DEFAULT_TEMPLATE = _find_template("Avalere_Doc_template.docx")

# Canonical template in the public repo, used only when no local copy is bundled
# (e.g. a slim skill bundle). Override with the env var if the repo or path moves.
TEMPLATE_URL = os.environ.get(
    "AVALERE_DOCX_TEMPLATE_URL",
    "https://raw.githubusercontent.com/nickclaw0/Intelligence-Layer-Prototype-Claude/"
    "main/wiki/skills/_assets/Avalere_Doc_template.docx",
)


def _ensure_template(path):
    """Return a readable template path. Local files always win: a bundled or repo
    template is used as-is and the engine works fully offline. Only when no local
    template exists (a slim bundle) do we fetch the canonical one from the public
    repo and cache it, so the template is never embedded yet never drifts."""
    if path and os.path.exists(path):
        return path
    if not TEMPLATE_URL:
        raise SystemExit("template not found at %s and AVALERE_DOCX_TEMPLATE_URL is empty." % path)
    cache_dir = os.path.join(tempfile.gettempdir(), "velorixa-avalere-assets")
    cache = os.path.join(cache_dir, os.path.basename(path) or "Avalere_Doc_template.docx")
    if os.path.exists(cache) and os.path.getsize(cache) > 0:
        return cache
    try:
        os.makedirs(cache_dir, exist_ok=True)
        urllib.request.urlretrieve(TEMPLATE_URL, cache)
    except Exception as e:
        raise SystemExit(
            "template not found locally and could not be fetched from %s: %s. Run where "
            "outbound network to raw.githubusercontent.com is allowed, set AVALERE_DOCX_TEMPLATE_URL, "
            "or install the offline skill bundle that ships the template under assets/." % (TEMPLATE_URL, e)
        )
    if not (os.path.exists(cache) and os.path.getsize(cache) > 0):
        raise SystemExit("template download from %s produced no file." % TEMPLATE_URL)
    return cache

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _norm(s):
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def read_styles(zin):
    """Return (rows, resolver-maps).
    rows: list of (type, styleId, name) for list-styles.
    by_name / by_id: normalised name/styleId -> styleId."""
    root = ET.fromstring(zin.read("word/styles.xml"))
    rows = []
    by_name = {}
    by_id = {}
    for st in root.findall("{%s}style" % W):
        sid = st.get("{%s}styleId" % W)
        typ = st.get("{%s}type" % W)
        nm_el = st.find("{%s}name" % W)
        nm = nm_el.get("{%s}val" % W) if nm_el is not None else sid
        rows.append((typ, sid, nm))
        if nm:
            by_name[_norm(nm)] = sid
        if sid:
            by_id.setdefault(_norm(sid), sid)
    return rows, by_name, by_id


def resolve_style(by_name, by_id, requested, default="Normal"):
    r = _norm(requested)
    if r in by_name:
        return by_name[r]
    if r in by_id:
        return by_id[r]
    for k, v in by_name.items():
        if r in k:
            return v
    return default


def cite_suffix(citations):
    return (" " + " ".join("[src:%s]" % c for c in citations)) if citations else ""


def paragraph_xml(style_id, text):
    return ('<w:p><w:pPr><w:pStyle w:val="%s"/></w:pPr>'
            '<w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p>'
            % (esc(style_id), esc(text)))


def cell_xml(text, style_id):
    return ('<w:tc><w:tcPr/><w:p><w:pPr><w:pStyle w:val="%s"/></w:pPr>'
            '<w:r><w:t xml:space="preserve">%s</w:t></w:r></w:p></w:tc>'
            % (esc(style_id), esc(text)))


def table_xml(style_id, rows, header_style_id=None, body_style_id="Normal"):
    """Render a w:tbl in the template's named table style. rows is a list of rows,
    each a list of cell strings. The first row is the header when header_style_id is set.
    A trailing empty paragraph is emitted so the table is never adjacent to <w:sectPr>
    or another table, which Word requires."""
    rows = [r for r in (rows or [])]
    if not rows:
        return ""
    ncols = max(len(r) for r in rows)
    grid = "".join('<w:gridCol w:w="%d"/>' % (9360 // ncols) for _ in range(ncols))
    trs = []
    for i, row in enumerate(rows):
        cells = list(row) + [""] * (ncols - len(row))
        sid = header_style_id if (i == 0 and header_style_id) else body_style_id
        trs.append("<w:tr>%s</w:tr>" % "".join(cell_xml(str(c), sid) for c in cells))
    return ('<w:tbl><w:tblPr><w:tblStyle w:val="%s"/><w:tblW w:w="0" w:type="auto"/></w:tblPr>'
            '<w:tblGrid>%s</w:tblGrid>%s</w:tbl><w:p/>'
            % (esc(style_id), grid, "".join(trs)))


def build(spec, template_path, out_override=None):
    template_path = _ensure_template(template_path)
    zin = zipfile.ZipFile(template_path)
    rows, by_name, by_id = read_styles(zin)

    doc = zin.read("word/document.xml").decode("utf-8")

    # locate the body content region: just after <w:body ...> up to the body-level <w:sectPr ...>
    bm = re.search(r"<w:body[^>]*>", doc)
    if not bm:
        raise SystemExit("template has no <w:body>")
    body_start = bm.end()
    sect_start = doc.rfind("<w:sectPr")
    if sect_start == -1:
        raise SystemExit("template has no body-level <w:sectPr>")

    paras = []
    for block in spec.get("blocks", []):
        if block.get("type") == "table":
            tstyle = resolve_style(by_name, by_id,
                                   block.get("style", "1 by 1 Grey with Orange Rule"), default="TableGrid")
            hstyle = (resolve_style(by_name, by_id, "Body Bold", default="Normal")
                      if block.get("header") else None)
            bstyle = resolve_style(by_name, by_id, block.get("cell_style", "Normal"))
            paras.append(table_xml(tstyle, block.get("rows", []), hstyle, bstyle))
        else:
            style_id = resolve_style(by_name, by_id, block.get("style", "Normal"))
            text = block.get("text", "") + cite_suffix(block.get("citations", []) or [])
            paras.append(paragraph_xml(style_id, text))
    new_body = "".join(paras)

    if not spec.get("clear_template_body", True):
        new_body = doc[body_start:sect_start] + new_body

    doc_out = doc[:body_start] + new_body + doc[sect_start:]

    out = out_override or spec.get("output", "document.docx")
    if not os.path.isabs(out):
        out = os.path.join(os.getcwd(), out)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == "word/document.xml":
                zout.writestr(item, doc_out)
            else:
                zout.writestr(item, zin.read(item.filename))
    zin.close()
    return out, len(spec.get("blocks", []))


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "list-styles":
        tpl = _ensure_template(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_TEMPLATE)
        with zipfile.ZipFile(tpl) as z:
            rows, _, _ = read_styles(z)
            for typ, sid, nm in rows:
                print("%s\t%s\t%s" % (typ, sid, nm))
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    spec = json.load(open(args.spec))
    out, n = build(spec, args.template, args.out)
    print("Wrote %s (%d blocks) from %s" % (out, n, os.path.basename(args.template)))


if __name__ == "__main__":
    main()
