#!/usr/bin/env python3
"""
generate-avalere-pptx build engine (template-as-base).

Starts from the pinned Avalere PowerPoint template, adds slides by selecting
existing named layouts from its 132-layout catalogue, and injects content into
the layout placeholders. The theme (Avalere Health 2025), the Inter fonts, and
every branded layout are preserved because we never rebuild geometry, we only
fill placeholders on the template's own layouts.

Pure standard library (zipfile + xml.etree): the runtime here is Python 3.9
with no third-party packages and no network, and a teammate cloning the repo
should not have to install anything. We open the .potx as a zip, keep every
master / layout / theme / font part byte-for-byte, drop the template's demo
slides, and write fresh slide parts whose text binds to the chosen layout's own
placeholders.

Usage:
    python3 build_deck.py <spec.json> [--template <path>] [--out <path>]
    python3 build_deck.py list-layouts [<template>]
    python3 build_deck.py describe-layout "<layout name>" [<template>]

Spec JSON shape:
{
  "output": "sample_deck.pptx",
  "title": "Deck title",
  "slides": [
    {
      "layout": "Cover - Pink - Custom",      # exact or fuzzy layout name
      "title": "Velorixa",
      "subtitle": "Brand strategy",           # simple layouts
      "bullets": ["point one", "point two"],  # simple layouts
      "citations": ["623851f2"],              # raw source ids, rendered as [src:id]
      "notes": "speaker notes"                # optional
    },
    {
      "layout": "3 Headered Columns - White", # rich layout: fill every slot by idx
      "title": "Three forces",
      "placeholders": [                       # idx values come from `describe-layout`
        {"idx": 12, "text": "subheading"},
        {"idx": 26, "paragraphs": [{"text": "Header", "level": 0},
                                   {"text": "point", "level": 1}]},
        {"idx": 30, "paragraphs": ["..."], "citations": ["623851f2"]}
      ]
    }
  ]
}

Layout names are read from the template at build time. Use list-layouts to print
the catalogue, and describe-layout to see a layout's fillable slots (idx, role, hint)
so rich layouts (columns, stats panels, sections, splits) fully populate instead of
collapsing into one box.
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


DEFAULT_TEMPLATE = _find_template("Avalere_PPT_template.potx")

# Canonical template in the public repo, used only when no local copy is bundled
# (e.g. a slim skill bundle). Override with the env var if the repo or path moves.
TEMPLATE_URL = os.environ.get(
    "AVALERE_PPTX_TEMPLATE_URL",
    "https://raw.githubusercontent.com/nickclaw0/Intelligence-Layer-Prototype-Claude/"
    "main/wiki/skills/_assets/Avalere_PPT_template.potx",
)


def _ensure_template(path):
    """Return a readable template path. Local files always win: a bundled or repo
    template is used as-is and the engine works fully offline. Only when no local
    template exists (a slim bundle) do we fetch the canonical one from the public
    repo and cache it, so the template is never embedded yet never drifts."""
    if path and os.path.exists(path):
        return path
    if not TEMPLATE_URL:
        raise SystemExit("template not found at %s and AVALERE_PPTX_TEMPLATE_URL is empty." % path)
    cache_dir = os.path.join(tempfile.gettempdir(), "velorixa-avalere-assets")
    cache = os.path.join(cache_dir, os.path.basename(path) or "Avalere_PPT_template.potx")
    if os.path.exists(cache) and os.path.getsize(cache) > 0:
        return cache
    try:
        os.makedirs(cache_dir, exist_ok=True)
        urllib.request.urlretrieve(TEMPLATE_URL, cache)
    except Exception as e:
        raise SystemExit(
            "template not found locally and could not be fetched from %s: %s. Run where "
            "outbound network to raw.githubusercontent.com is allowed, set AVALERE_PPTX_TEMPLATE_URL, "
            "or install the offline skill bundle that ships the template under assets/." % (TEMPLATE_URL, e)
        )
    if not (os.path.exists(cache) and os.path.getsize(cache) > 0):
        raise SystemExit("template download from %s produced no file." % TEMPLATE_URL)
    return cache

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
SLIDE_CT = "application/vnd.openxmlformats-officedocument.presentationml.slide+xml"
NOTES_CT = "application/vnd.openxmlformats-officedocument.presentationml.notesSlide+xml"
SLIDE_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide"
LAYOUT_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout"
NOTES_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesSlide"
NOTESMASTER_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/notesMaster"

DEFAULT_LAYOUT = "Title and Content - White"
SLIDE_W = 12192000
SLIDE_H = 6858000


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _norm(s):
    """Lowercase and collapse dash variants/whitespace so specs can use plain hyphens."""
    s = s.replace("–", "-").replace("—", "-")
    return re.sub(r"\s+", " ", s).strip().lower()


def layout_files(zin):
    """name -> 'slideLayoutN.xml', across the layouts in the package."""
    out = {}
    for n in zin.namelist():
        if re.match(r"ppt/slideLayouts/slideLayout\d+\.xml$", n):
            root = ET.fromstring(zin.read(n))
            csld = root.find("{%s}cSld" % P)
            name = csld.get("name") if csld is not None else os.path.basename(n)
            out[name.strip()] = os.path.basename(n)
    return out


def pick_layout(lmap, requested):
    """Exact match, else dash/case-insensitive, else first whose normalised name contains the request."""
    if requested in lmap:
        return lmap[requested]
    norm = {_norm(k): v for k, v in lmap.items()}
    r = _norm(requested)
    if r in norm:
        return norm[r]
    for k, v in norm.items():
        if r in k:
            return v
    raise SystemExit("Layout not found: %r. Run with 'list-layouts' to see options." % requested)


def layout_placeholders(zin, layout_file):
    """Parse a layout's placeholders -> list of {type, has_type, idx, x, y, cx, cy, prompt}.
    The template marks its main content area as a generic (typeless) placeholder. x/y/cx/cy
    are the layout geometry (EMU) so callers can tell a left column from a right one; prompt is
    the layout's own placeholder text, a strong hint for what belongs there."""
    root = ET.fromstring(zin.read("ppt/slideLayouts/" + layout_file))
    phs = []
    for sp in root.iter("{%s}sp" % P):
        ph = sp.find(".//{%s}nvPr/{%s}ph" % (P, P))
        if ph is None:
            continue
        x = y = cx = cy = 0
        off = sp.find(".//{%s}spPr/{%s}xfrm/{%s}off" % (A, A, A))
        ext = sp.find(".//{%s}spPr/{%s}xfrm/{%s}ext" % (A, A, A))
        if off is not None:
            x, y = int(off.get("x", 0)), int(off.get("y", 0))
        if ext is not None:
            cx, cy = int(ext.get("cx", 0)), int(ext.get("cy", 0))
        prompt = ""
        tx = sp.find(".//{%s}txBody" % P)
        if tx is not None:
            prompt = " ".join(t.text for t in tx.iter("{%s}t" % A) if t.text).strip()
        phs.append({"type": ph.get("type", "body"), "has_type": ph.get("type") is not None,
                    "idx": ph.get("idx"), "x": x, "y": y, "cx": cx, "cy": cy, "prompt": prompt})
    return phs


def pick_bindings(phs):
    """Choose placeholders for title / subtitle / content (bullets)."""
    title = next((p for p in phs if p["type"] in ("title", "ctrTitle")), None)
    cands = [p for p in phs if p["type"] not in ("title", "ctrTitle", "ftr", "sldNum", "pic", "dt")]
    subtitle_typed = next((p for p in cands if p["type"] in ("subTitle",)), None)
    generic = [p for p in cands if not p["has_type"]]
    content = (max(generic, key=lambda p: p["cy"]) if generic
               else (max(cands, key=lambda p: p["cy"]) if cands else None))
    subtitle = subtitle_typed
    if subtitle is None:
        for p in cands:
            if p is not content:
                subtitle = p
                break
    return title, subtitle, content


def cite_suffix(citations):
    return (" " + " ".join("[src:%s]" % c for c in citations)) if citations else ""


def ph_shape(shape_id, name, ph_type, ph_idx, paragraphs, emit_type=True):
    if ph_type in ("title", "ctrTitle"):
        ph = '<p:ph type="%s"/>' % ph_type
    elif ph_idx is not None and emit_type and ph_type:
        ph = '<p:ph type="%s" idx="%s"/>' % (ph_type, ph_idx)
    elif ph_idx is not None:
        ph = '<p:ph idx="%s"/>' % ph_idx
    else:
        ph = '<p:ph type="%s"/>' % (ph_type or "body")
    paras = []
    for para in paragraphs:
        # a paragraph may be a plain string, or {"text": ..., "level": N} / (text, level) for sub-bullets
        if isinstance(para, dict):
            text, level = para.get("text", ""), int(para.get("level", 0) or 0)
        elif isinstance(para, (list, tuple)):
            text, level = (para[0] if para else ""), (int(para[1]) if len(para) > 1 else 0)
        else:
            text, level = para, 0
        ppr = ('<a:pPr lvl="%d"/>' % level) if level else ""
        if text == "":
            paras.append('<a:p>%s<a:endParaRPr lang="en-GB"/></a:p>' % ppr)
        else:
            paras.append('<a:p>%s<a:r><a:rPr lang="en-GB" dirty="0"/><a:t>%s</a:t></a:r></a:p>'
                         % (ppr, esc(text)))
    if not paras:
        paras.append('<a:p><a:endParaRPr lang="en-GB"/></a:p>')
    return ('<p:sp><p:nvSpPr><p:cNvPr id="%d" name="%s"/>'
            '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
            '<p:nvPr>%s</p:nvPr></p:nvSpPr>'
            '<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>%s</p:txBody></p:sp>'
            % (shape_id, esc(name), ph, "".join(paras)))


def build_slide_xml(spec, phs):
    title, subtitle, content = pick_bindings(phs)
    by_idx = {p["idx"]: p for p in phs if p["idx"] is not None}
    title_text = spec.get("title", "")
    cites = spec.get("citations", []) or []
    shapes = []
    sid = 2
    filled = set()  # idx values already filled, so auto-binding never double-fills

    if title is not None and title_text:
        shapes.append(ph_shape(sid, "Title %d" % sid, "title", title["idx"], [title_text]))
        sid += 1

    # Rich mode: explicit per-placeholder content. Each entry targets a layout placeholder by
    # idx (see `describe-layout`) and carries `text` or `paragraphs` (strings, or {text, level}
    # for sub-bullets). This is what lets columns, stats panels, sections, and splits fully
    # populate instead of collapsing into one box.
    for entry in (spec.get("placeholders") or []):
        idx = entry.get("idx")
        idx = str(idx) if idx is not None else None
        ph = by_idx.get(idx)
        if ph is None:
            continue
        paras = entry.get("paragraphs")
        if paras is None:
            t = entry.get("text", "")
            paras = [t] if t != "" else []
        else:
            paras = list(paras)
        if entry.get("citations"):
            paras = paras + ["Sources:" + cite_suffix(entry["citations"])]
        if not paras:
            continue
        shapes.append(ph_shape(sid, "Content Placeholder %d" % sid, ph["type"], ph["idx"],
                               paras, emit_type=ph["has_type"]))
        filled.add(idx)
        sid += 1

    # Simple mode (backward compatible): subtitle + bullets auto-bound to the picked placeholders,
    # only where the rich mode has not already filled that placeholder.
    sub_text = spec.get("subtitle")
    bullets = list(spec.get("bullets", []) or [])
    sub_into_content = False
    if sub_text:
        if subtitle is not None and subtitle["idx"] not in filled:
            stext = sub_text + (cite_suffix(cites) if not bullets else "")
            shapes.append(ph_shape(sid, "Text Placeholder %d" % sid, subtitle["type"],
                                   subtitle["idx"], [stext], emit_type=subtitle["has_type"]))
            filled.add(subtitle["idx"])
            sid += 1
        elif content is not None and not bullets and content["idx"] not in filled:
            sub_into_content = True

    paras = []
    if sub_into_content:
        paras.append(sub_text + cite_suffix(cites))
    if bullets:
        if len(bullets) == 1:
            paras.append(bullets[0] + cite_suffix(cites))
        else:
            paras.extend(bullets)
            if cites:
                paras.append("Sources:" + cite_suffix(cites))

    if content is not None and paras and content["idx"] not in filled:
        shapes.append(ph_shape(sid, "Content Placeholder %d" % sid, content["type"],
                               content["idx"], paras, emit_type=content["has_type"]))
        sid += 1

    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:sld xmlns:a="%s" xmlns:r="%s" xmlns:p="%s"><p:cSld><p:spTree>'
            '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            '%s</p:spTree></p:cSld>'
            '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
            % (A, R, P, "".join(shapes)))


def notes_xml(slide_no, note_text):
    paras = []
    for line in note_text.split("\n"):
        if line.strip():
            paras.append('<a:p><a:r><a:rPr lang="en-US" dirty="0"/><a:t>%s</a:t></a:r></a:p>' % esc(line))
    if not paras:
        return None
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
            '<p:notes xmlns:a="%s" xmlns:r="%s" xmlns:p="%s"><p:cSld><p:spTree>'
            '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
            '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
            '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
            '<p:sp><p:nvSpPr><p:cNvPr id="2" name="Notes Placeholder 2"/>'
            '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
            '<p:nvPr><p:ph type="body" idx="1"/></p:nvPr></p:nvSpPr>'
            '<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>%s</p:txBody></p:sp>'
            '</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:notes>'
            % (A, R, P, "".join(paras)))


def notesmaster_target(zin):
    """Find the notesMaster part path so notes slides can reference it."""
    for n in zin.namelist():
        if re.match(r"ppt/notesMasters/notesMaster\d+\.xml$", n):
            return os.path.basename(n)
    return None


def build(spec, template_path, out_override=None):
    template_path = _ensure_template(template_path)
    zin = zipfile.ZipFile(template_path)
    names = zin.namelist()
    lmap = layout_files(zin)
    nmaster = notesmaster_target(zin)

    pres = zin.read("ppt/presentation.xml").decode("utf-8")
    pres_rels = zin.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
    ctypes = zin.read("[Content_Types].xml").decode("utf-8")

    used = [int(m) for m in re.findall(r'Id="rId(\d+)"', pres_rels)]
    next_rid = (max(used) + 1) if used else 1

    new_slides = []   # dict per slide: part, xml, rels(list of (id,type,target)), prid, sldid, notes_part, notes_xml
    sldid = 256
    for i, s in enumerate(spec.get("slides", []), start=1):
        layout_file = pick_layout(lmap, s.get("layout", DEFAULT_LAYOUT))
        phs = layout_placeholders(zin, layout_file)
        xml = build_slide_xml(s, phs)
        part = "ppt/slides/slide%d.xml" % i

        # slide notes (notes + source ids), if any
        cites = s.get("citations", []) or []
        note_parts = [x for x in (s.get("notes"),
                                  ("Sources: " + ", ".join(cites)) if cites else "") if x]
        nxml = notes_xml(i, "\n".join(note_parts)) if note_parts and nmaster else None

        slide_rels = [("rId1", LAYOUT_REL, "../slideLayouts/" + layout_file)]
        notes_part = None
        if nxml is not None:
            notes_part = "ppt/notesSlides/notesSlide%d.xml" % i
            slide_rels.append(("rId2", NOTES_REL, "../notesSlides/notesSlide%d.xml" % i))

        prid = "rId%d" % next_rid
        next_rid += 1
        new_slides.append({"part": part, "xml": xml, "slide_rels": slide_rels,
                           "prid": prid, "sldid": sldid,
                           "notes_part": notes_part, "notes_xml": nxml,
                           "layout_file": layout_file})
        sldid += 1

    # presentation.xml: rebuild sldIdLst
    sld_entries = "".join('<p:sldId id="%d" r:id="%s"/>' % (n["sldid"], n["prid"]) for n in new_slides)
    if "<p:sldIdLst" in pres:
        pres = re.sub(r"<p:sldIdLst>.*?</p:sldIdLst>", "<p:sldIdLst>%s</p:sldIdLst>" % sld_entries, pres, flags=re.S)
    else:
        pres = pres.replace("</p:sldMasterIdLst>", "</p:sldMasterIdLst><p:sldIdLst>%s</p:sldIdLst>" % sld_entries, 1)

    # presentation rels: drop old slide rels, add new
    pres_rels = re.sub(r'<Relationship[^>]*Type="[^"]*/slide"[^>]*/>', "", pres_rels)
    add_rels = "".join('<Relationship Id="%s" Type="%s" Target="slides/slide%d.xml"/>'
                       % (n["prid"], SLIDE_REL, i + 1) for i, n in enumerate(new_slides))
    pres_rels = pres_rels.replace("</Relationships>", add_rels + "</Relationships>")

    # content types: drop old slide + notes overrides, flip presentation CT, add new slides + notes
    ctypes = re.sub(r'<Override PartName="/ppt/slides/slide\d+\.xml"[^>]*/>', "", ctypes)
    ctypes = re.sub(r'<Override PartName="/ppt/notesSlides/notesSlide\d+\.xml"[^>]*/>', "", ctypes)
    ctypes = ctypes.replace("presentationml.template.main+xml", "presentationml.presentation.main+xml")
    add_ov = []
    for n in new_slides:
        add_ov.append('<Override PartName="/%s" ContentType="%s"/>' % (n["part"], SLIDE_CT))
        if n["notes_part"]:
            add_ov.append('<Override PartName="/%s" ContentType="%s"/>' % (n["notes_part"], NOTES_CT))
    ctypes = ctypes.replace("</Types>", "".join(add_ov) + "</Types>")

    out = out_override or spec.get("output", "deck.pptx")
    if not os.path.isabs(out):
        out = os.path.join(os.getcwd(), out)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)

    existing_slides = [x for x in names if re.match(r"ppt/slides/slide\d+\.xml$", x)]
    existing_notes = [x for x in names if re.match(r"ppt/notesSlides/notesSlide\d+\.xml$", x)]
    drop = set(existing_slides) | set(existing_notes)
    drop |= {"ppt/slides/_rels/%s.rels" % os.path.basename(s) for s in existing_slides}
    drop |= {"ppt/notesSlides/_rels/%s.rels" % os.path.basename(s) for s in existing_notes}
    drop |= {"ppt/presentation.xml", "ppt/_rels/presentation.xml.rels", "[Content_Types].xml"}

    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename in drop:
                continue
            zout.writestr(item, zin.read(item.filename))
        zout.writestr("[Content_Types].xml", ctypes)
        zout.writestr("ppt/presentation.xml", pres)
        zout.writestr("ppt/_rels/presentation.xml.rels", pres_rels)
        for n in new_slides:
            zout.writestr(n["part"], n["xml"])
            rels = "".join('<Relationship Id="%s" Type="%s" Target="%s"/>' % r for r in n["slide_rels"])
            zout.writestr("ppt/slides/_rels/%s.rels" % os.path.basename(n["part"]),
                          '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                          '<Relationships xmlns="%s">%s</Relationships>' % (PR, rels))
            if n["notes_part"]:
                zout.writestr(n["notes_part"], n["notes_xml"])
                nrels = ('<Relationship Id="rId1" Type="%s" Target="../slides/%s"/>'
                         % (SLIDE_REL, os.path.basename(n["part"])))
                nrels += ('<Relationship Id="rId2" Type="%s" Target="../notesMasters/%s"/>'
                          % (NOTESMASTER_REL, nmaster))
                zout.writestr("ppt/notesSlides/_rels/%s.rels" % os.path.basename(n["notes_part"]),
                              '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                              '<Relationships xmlns="%s">%s</Relationships>' % (PR, nrels))
    zin.close()
    return out, len(new_slides)


def describe_layout(template, name):
    """Print every fillable placeholder on a layout: its idx, role, position, and the layout's
    own prompt text. The model reads this, then targets each idx via the slide's 'placeholders'
    list so rich layouts (columns, stats panels, sections, splits) fully populate."""
    tpl = _ensure_template(template)
    with zipfile.ZipFile(tpl) as z:
        lf = pick_layout(layout_files(z), name)
        phs = layout_placeholders(z, lf)

    def pos(p):
        if not p["cx"]:
            return ""
        cxmid, cymid = p["x"] + p["cx"] // 2, p["y"] + p["cy"] // 2
        col = "left" if cxmid < SLIDE_W / 3 else ("right" if cxmid > 2 * SLIDE_W / 3 else "center")
        row = "top" if cymid < SLIDE_H / 3 else ("bottom" if cymid > 2 * SLIDE_H / 3 else "middle")
        return "%s-%s" % (row, col)

    chrome = ("ftr", "sldNum", "dt", "pic")
    print("Layout: %s  ->  %s" % (name, lf))
    print("Fill the title with the slide 'title' field. Fill every other slot via the slide's")
    print("'placeholders': [{\"idx\": N, \"paragraphs\": [...]}] — one entry per idx below.")
    print("Slots are listed in document order, which is normally left-to-right then top-to-bottom.")
    print("The prompt text is the strongest hint for what belongs in each slot (e.g. '##%' = a stat figure).\n")
    for p in phs:
        if p["type"] in ("title", "ctrTitle"):
            print("  (title)  role=TITLE     -> use the slide 'title' field")
            continue
        if p["type"] in chrome:
            continue  # footers / slide numbers / dates are template chrome, do not fill
        role = ("subtitle" if p["type"] == "subTitle"
                else "content" if not p["has_type"] else p["type"])
        hint = ("  hint=%r" % p["prompt"][:52]) if p["prompt"] else ""
        loc = ("  pos=%s" % pos(p)) if pos(p) else ""
        print("  idx=%-4s role=%-8s%s%s" % (p["idx"], role, loc, hint))


def main():
    if len(sys.argv) >= 3 and sys.argv[1] == "describe-layout":
        describe_layout(sys.argv[3] if len(sys.argv) > 3 else DEFAULT_TEMPLATE, sys.argv[2])
        return
    if len(sys.argv) >= 2 and sys.argv[1] == "list-layouts":
        tpl = _ensure_template(sys.argv[2] if len(sys.argv) > 2 else DEFAULT_TEMPLATE)
        with zipfile.ZipFile(tpl) as z:
            for name in sorted(layout_files(z)):
                print(name)
        return
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    spec = json.load(open(args.spec))
    out, n = build(spec, args.template, args.out)
    print("Wrote %s (%d slides) from %s" % (out, n, os.path.basename(args.template)))


if __name__ == "__main__":
    main()
