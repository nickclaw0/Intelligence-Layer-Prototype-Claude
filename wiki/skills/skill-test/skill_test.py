#!/usr/bin/env python3
"""
skill-test engine.

Run a skill against a known input (its sample_spec.json) and check the output
structure before the skill is committed. Currently knows how to exercise the
document-producing skills (generate-avalere-pptx, generate-avalere-docx) and to
lint any SKILL.md frontmatter.

Usage:
    python3 skill_test.py <skill-dir-name|all>
"""
import sys, os, json, subprocess, tempfile, glob, zipfile, re
import xml.etree.ElementTree as ET

SKILLS_DIR = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REQUIRED_FRONTMATTER = ["name", "description", "triggers", "required_tools", "outputs", "sensitivity"]


def check_frontmatter(skill_dir):
    path = os.path.join(skill_dir, "SKILL.md")
    if not os.path.exists(path):
        return [f"missing SKILL.md"]
    txt = open(path, encoding="utf-8").read()
    if not txt.startswith("---"):
        return ["SKILL.md has no frontmatter block"]
    fm = txt.split("---", 2)[1]
    problems = [f"frontmatter missing '{k}'" for k in REQUIRED_FRONTMATTER if f"{k}:" not in fm]
    if "client:" not in fm:
        problems.append("frontmatter missing 'client' (client-portability rule: every skill is tenant-scoped)")
    return problems


def run_builder(skill_dir, builder, validator):
    spec = os.path.join(skill_dir, "sample_spec.json")
    if not os.path.exists(spec):
        return [f"no sample_spec.json to test against"]
    out = tempfile.mktemp(suffix=os.path.splitext(json.load(open(spec)).get("output", "out.bin"))[1])
    r = subprocess.run([sys.executable, os.path.join(skill_dir, builder), spec, "--out", out],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return [f"builder failed: {r.stderr.strip()[:200]}"]
    if not os.path.exists(out) or os.path.getsize(out) == 0:
        return ["builder produced no output"]
    return validator(out)


def validate_pptx(path):
    """Pure-stdlib structural check: valid zip, every part parses, the presentation
    is a real presentation (not a template), and the slide list is non-empty with
    each referenced slide part present."""
    problems = []
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:
        return ["output is not a valid zip: %s" % e]
    if z.testzip() is not None:
        problems.append("zip has a corrupt member")
    names = set(z.namelist())
    for n in (n for n in names if n.endswith(".xml") or n.endswith(".rels")):
        try:
            ET.fromstring(z.read(n))
        except Exception as e:
            problems.append("part does not parse: %s (%s)" % (n, e))
    ct = z.read("[Content_Types].xml").decode("utf-8")
    if "presentationml.presentation.main+xml" not in ct:
        problems.append("presentation content-type not flipped to a presentation")
    pres = ET.fromstring(z.read("ppt/presentation.xml"))
    sldlst = pres.find("{%s}sldIdLst" % P_NS)
    ids = list(sldlst) if sldlst is not None else []
    if not ids:
        problems.append("deck has no slides")
    rels = z.read("ppt/_rels/presentation.xml.rels").decode("utf-8")
    relmap = dict(re.findall(r'Id="(rId\d+)"[^>]*Target="([^"]+)"', rels))
    rkey = "{%s}id" % "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    for sid in ids:
        tgt = relmap.get(sid.get(rkey))
        if not tgt or ("ppt/" + tgt) not in names:
            problems.append("slide reference %s does not resolve to a part" % sid.get(rkey))
    return problems


def validate_docx(path):
    """Pure-stdlib structural check: valid zip, every part parses, the body has
    at least one non-empty paragraph, and the section properties (header/footer
    wiring) survive."""
    problems = []
    try:
        z = zipfile.ZipFile(path)
    except Exception as e:
        return ["output is not a valid zip: %s" % e]
    if z.testzip() is not None:
        problems.append("zip has a corrupt member")
    for n in (n for n in z.namelist() if n.endswith(".xml") or n.endswith(".rels")):
        try:
            ET.fromstring(z.read(n))
        except Exception as e:
            problems.append("part does not parse: %s (%s)" % (n, e))
    root = ET.fromstring(z.read("word/document.xml"))
    body = root.find("{%s}body" % W_NS)
    paras = body.findall("{%s}p" % W_NS) if body is not None else []
    nonempty = [p for p in paras if "".join(t.text or "" for t in p.iter("{%s}t" % W_NS)).strip()]
    if not nonempty:
        problems.append("document has no content paragraphs")
    if body is None or body.find("{%s}sectPr" % W_NS) is None:
        problems.append("document lost its section properties (header/footer wiring)")
    return problems


BUILDERS = {
    "generate-avalere-pptx": ("build_deck.py", validate_pptx),
    "generate-avalere-docx": ("build_doc.py", validate_docx),
}


def test_skill(name):
    skill_dir = os.path.join(SKILLS_DIR, name)
    if not os.path.isdir(skill_dir):
        return [f"no such skill: {name}"]
    problems = check_frontmatter(skill_dir)
    if name in BUILDERS:
        builder, validator = BUILDERS[name]
        problems += run_builder(skill_dir, builder, validator)
    return problems


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: skill_test.py <skill-dir-name|all>")
    target = sys.argv[1]
    names = ([os.path.basename(os.path.dirname(p)) for p in glob.glob(os.path.join(SKILLS_DIR, "*", "SKILL.md"))]
             if target == "all" else [target])
    failed = 0
    for name in sorted(names):
        problems = test_skill(name)
        if problems:
            failed += 1
            print(f"FAIL  {name}")
            for p in problems:
                print(f"      - {p}")
        else:
            print(f"PASS  {name}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
