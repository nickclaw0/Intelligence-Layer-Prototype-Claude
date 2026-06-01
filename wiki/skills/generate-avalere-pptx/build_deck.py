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

Spec JSON shape:
{
  "output": "sample_deck.pptx",
  "title": "Deck title",
  "slides": [
    {
      "layout": "Cover - Pink - Custom",     # exact or fuzzy layout name
      "title": "Velorixa",
      "subtitle": "Brand strategy",
      "bullets": ["point one", "point two"], # optional
      "citations": ["623851f2"],              # raw source ids, rendered as [src:id]
      "notes": "speaker notes"                # optional
    }
  ]
}

Layout names are read from the template at build time. Use list-layouts to
print the catalogue.
"""
import sys, os, json, argparse, zipfile, re
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TEMPLATE = os.path.normpath(os.path.join(HERE, "..", "_assets", "Avalere_PPT_template.potx"))

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
    """Parse a layout's placeholders -> list of {type, has_type, idx, cy}.
    The template marks its main content area as a generic (typeless) placeholder."""
    root = ET.fromstring(zin.read("ppt/slideLayouts/" + layout_file))
    phs = []
    for sp in root.iter("{%s}sp" % P):
        ph = sp.find(".//{%s}nvPr/{%s}ph" % (P, P))
        if ph is None:
            continue
        cy = 0
        ext = sp.find(".//{%s}spPr/{%s}xfrm/{%s}ext" % (A, A, A))
        if ext is not None and ext.get("cy"):
            cy = int(ext.get("cy"))
        phs.append({"type": ph.get("type", "body"), "has_type": ph.get("type") is not None,
                    "idx": ph.get("idx"), "cy": cy})
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
    for text in paragraphs:
        if text == "":
            paras.append('<a:p><a:endParaRPr lang="en-GB"/></a:p>')
        else:
            paras.append('<a:p><a:r><a:rPr lang="en-GB" dirty="0"/><a:t>%s</a:t></a:r></a:p>' % esc(text))
    if not paras:
        paras.append('<a:p><a:endParaRPr lang="en-GB"/></a:p>')
    return ('<p:sp><p:nvSpPr><p:cNvPr id="%d" name="%s"/>'
            '<p:cNvSpPr><a:spLocks noGrp="1"/></p:cNvSpPr>'
            '<p:nvPr>%s</p:nvPr></p:nvSpPr>'
            '<p:spPr/><p:txBody><a:bodyPr/><a:lstStyle/>%s</p:txBody></p:sp>'
            % (shape_id, esc(name), ph, "".join(paras)))


def build_slide_xml(spec, phs):
    title, subtitle, content = pick_bindings(phs)
    title_text = spec.get("title", "")
    sub_text = spec.get("subtitle")
    bullets = list(spec.get("bullets", []) or [])
    cites = spec.get("citations", []) or []
    shapes = []
    sid = 2

    if title is not None and title_text:
        shapes.append(ph_shape(sid, "Title %d" % sid, "title", title["idx"], [title_text]))
        sid += 1

    # subtitle: dedicated placeholder if present; else fold into content when no bullets
    sub_into_content = False
    if sub_text:
        if subtitle is not None:
            stext = sub_text + (cite_suffix(cites) if not bullets else "")
            shapes.append(ph_shape(sid, "Text Placeholder %d" % sid, subtitle["type"],
                                   subtitle["idx"], [stext], emit_type=subtitle["has_type"]))
            sid += 1
        elif content is not None and not bullets:
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

    if content is not None and paras:
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


def main():
    if len(sys.argv) >= 2 and sys.argv[1] == "list-layouts":
        tpl = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_TEMPLATE
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
