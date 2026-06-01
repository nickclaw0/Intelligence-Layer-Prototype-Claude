---
name: generate-avalere-pptx
description: Produce a PowerPoint deck in the Avalere Health 2025 template, on-brand and cited from the wiki. Use this skill for ANY request to make a PowerPoint, deck, presentation, slides, or .pptx for Velorixa. Never build a deck by another method.
triggers:
  - query_patterns: ["build a deck", "make a deck", "create a deck", "deck about", "make a presentation", "create a presentation", "presentation about", "powerpoint", "power point", "ppt", "pptx", "avalere deck", "slides for", "make slides", "slide deck"]
  - event: project_page_marked_deck_needed
required_tools:
  - file_creation
  - drive_read
  - image_generation_passthrough
related_wiki:
  - projects/{active}
  - entities/{client}
inputs:
  - deck_title: string
  - slides: list           # each: layout name, title, subtitle/bullets, citations
outputs:
  - deck.pptx
sensitivity: inherits_from_project
client: velorixa
---

Produce a deck in the Avalere PowerPoint template, built on the anthropics/skills pptx pattern. The reliable way to hit the template exactly is the template-as-base approach: start from the supplied template file, place slides on its own named layouts, and inject content into the layout placeholders. Never generate from scratch and re-skin afterwards.

**This skill is the only sanctioned way to produce a Velorixa PowerPoint.** Whenever a deck, presentation, slides, or .pptx is requested, use this skill: gather the cited wiki content, write a spec, and run `build_deck.py`. Do not fall back to a generic deck, another PowerPoint tool, or building slide XML by hand.

## Base assets

- Template (pinned): the Avalere PowerPoint template (theme Avalere Health 2025, Inter font family, 132 named layouts). The engine finds it automatically: in this repo it is `../_assets/Avalere_PPT_template.potx`; in a self-contained skill bundle (for example installed on Claude.ai) it ships inside the skill folder at `assets/Avalere_PPT_template.potx`.
- Engine: `build_deck.py`.
- Layout catalogue: `layout_catalogue.md`. The engine also reads layout names from the template at build time, so the catalogue is a reference, not the source of truth.

## Running on Claude.ai (bundled, in code execution)

When this skill is installed on Claude.ai, it is self-contained: `build_deck.py` plus the pinned template under `assets/`. It runs in the code-execution sandbox with no install step (pure standard library on Python 3.9+). The flow: read the wiki for the content and its source IDs (via the connectors or the query skill), write the spec JSON, run `python3 build_deck.py spec.json --out deck.pptx`, and return the resulting branded `.pptx`. The template is read from the bundle, so the output is always on-brand.

## How to build

1. Read the relevant wiki pages (project, entities, concepts, sources) and gather the content and its source IDs. Every claim on a slide must trace to a source.
2. Decide a slide sequence and map each slide's intent to the closest-named layout. Read layout names with `python3 build_deck.py list-layouts`. Families: Cover (Pink, Turquoise/Lime, Cutout, Custom), Title and Content (White, Black, Pink, Turquoise/Lime, plus Corner Gradient, Slash, Wide Slash), Manifesto/Intro, Divider, Agenda, 2/3/4 Headered Columns, 6 Text Sections, Half Split, Third Split, Aframe Split, RHS/Bottom Stats Panels, Timeline, Team of 5/10/15/24, Large Statement, Case Study, Thank You, Title only, Blank.
3. Write a spec JSON (see `sample_spec.json`) with the deck title and a `slides` list. Each slide carries a `layout` name, a `title`, optional `subtitle` or `bullets`, and `citations` (raw source IDs). Layout matching is dash and case insensitive.
4. Run the engine:
   ```
   python3 build_deck.py <spec.json> --out <output.pptx>
   ```
   It opens the template, clears the template's demo slides while keeping all masters, layouts, and theme, adds a slide per spec entry on the chosen layout, fills the title and body placeholders, renders citations inline as `[src:id]`, and writes source IDs into the slide notes.
5. File a completion record back into the wiki: create a source-adjacent note under `synthesis/` or append to the project page recording the deck generated, the layouts used, and every source ID cited. Append a line to `log.md`.

## Rules

- Theme, fonts, and layout geometry come from the template. Do not set ad-hoc colours or fonts; let the layout carry the brand.
- Provenance is mandatory. A slide with an uncited factual claim is not allowed. If a claim cannot be sourced, drop it or flag for review.
- Sensitivity inherits from the project and its cited sources. A deck citing a confidential source is confidential and follows the gating rules in `../../CLAUDE.md`.
- This skill is authored for the Velorixa tenant. It is not reusable in another tenant without review and reauthoring.
