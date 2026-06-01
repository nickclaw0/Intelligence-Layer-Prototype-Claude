---
name: generate-avalere-docx
description: Produce a Word document in the Avalere template, on-brand and cited from the wiki. Use this skill for ANY request to make a Word document, .docx, one-pager, recap, brief, or write-up for Velorixa. Never build a document by another method.
triggers:
  - query_patterns: ["write a document", "write a doc", "draft a doc", "draft a document", "create a document", "word doc", "word document", "docx", "avalere doc", "one-pager", "one pager", "recap document", "write up", "write-up", "brief"]
  - event: project_page_marked_doc_needed
required_tools:
  - file_creation
  - drive_read
related_wiki:
  - projects/{active}
  - entities/{client}
inputs:
  - blocks: list           # each: style name, text, citations
outputs:
  - document.docx
sensitivity: inherits_from_project
client: velorixa
---

Produce a document in the Avalere Word template, built on the anthropics/skills docx pattern. Use the template-as-base approach: start from the supplied template file, clear its demo body while keeping the section properties, and add content using the template's own named styles. The brand comes from the template's styles, theme, header, footer, and logo, never from ad-hoc formatting.

**This skill is the only sanctioned way to produce a Velorixa Word document.** Whenever a document, .docx, one-pager, recap, or write-up is requested, use this skill: gather the cited wiki content, write a spec, and run `build_doc.py`. Do not fall back to a generic document or another tool.

## Base assets

- Template (pinned): the Avalere Word template (theme palette Custom 2, named styles, header/footer with embedded logo). The engine finds it automatically: in this repo it is `../_assets/Avalere_Doc_template.docx`; in a self-contained skill bundle (for example installed on Claude.ai) it ships inside the skill folder at `assets/Avalere_Doc_template.docx`.
- Engine: `build_doc.py`.
- Style reference: `styles_reference.md`. The engine also reads style names from the template at build time.

## Running on Claude.ai (in code execution)

When this skill is installed on Claude.ai it runs in the code-execution sandbox with no install step (pure standard library on Python 3.9+). The flow: read the wiki for the content and its source IDs (via the connectors or the query skill), write the spec JSON, run `python3 build_doc.py spec.json --out document.docx`, and return the resulting branded `.docx`.

The engine resolves the pinned template in this order: a co-located `assets/Avalere_Doc_template.docx` (bundled) or the repo's `../_assets/`, and if neither exists it downloads the canonical template once from the public repo (`AVALERE_DOCX_TEMPLATE_URL`, default `raw.githubusercontent.com/.../wiki/skills/_assets/Avalere_Doc_template.docx`) and caches it under the temp dir. The shipped bundle (`velorixa-avalere-docx-skill.zip`, ~88 KB) embeds the template under `assets/` so it works with no network; the download path is just a fallback if the template is ever missing. The Word template is small enough that there is no slim variant, unlike the PowerPoint skill. Either way the output is on-brand because the bytes are the same pinned template.

## How to build

1. Read the relevant wiki pages and gather content with its source IDs. Every factual claim must trace to a source.
2. Structure the document as a list of blocks, each mapped to a named style. Common styles: `Title` (25pt, Inter), `Subtitle` (Arial 11pt), `Heading 1` (20pt, Inter), `Heading 2` to `Heading 5` (Arial), `Normal` (Inter 10pt body), `List Bullet` 1 to 5, `List Number` 1 to 5, `Quote`, `Intense Quote`, `Body Bold`. Use the named styles rather than manual formatting.
3. Write a spec JSON (see `sample_spec.json`) with a `blocks` list. Each block has a `style`, `text`, and optional `citations` (raw source IDs). Style matching is dash and case insensitive.
4. Run the engine:
   ```
   python3 build_doc.py <spec.json> --out <output.docx>
   ```
   It opens the template, clears the demo body while preserving the trailing section properties (so `header1`, `footer1`, `footer2`, and the logo media survive), and adds each block as a paragraph in the named style, rendering citations inline as `[src:id]`.
5. File a completion record back into the wiki: record the document generated, the styles used, and every source ID cited, on the project page or a `synthesis/` note, and append a line to `log.md`.

## Rules

- All formatting comes from the template's named styles and theme. Do not hard-code fonts, sizes, or colours.
- Provenance is mandatory. No uncited factual claim. If a claim cannot be sourced, drop it or flag for review.
- Sensitivity inherits from the project and its cited sources, and follows the gating rules in `../../CLAUDE.md`.
- Authored for the Velorixa tenant. Not reusable in another tenant without review and reauthoring.
