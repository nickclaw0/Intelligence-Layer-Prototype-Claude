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

## Running on Claude.ai (in code execution)

When this skill is installed on Claude.ai it runs in the code-execution sandbox with no install step (pure standard library on Python 3.9+). The flow: read the wiki for the content and its source IDs (via the connectors or the query skill), write the spec JSON, run `python3 build_deck.py spec.json --out deck.pptx`, and return the resulting branded `.pptx`.

The engine resolves the pinned template in this order: a co-located `assets/Avalere_PPT_template.potx` (offline bundle) or the repo's `../_assets/`, and if neither exists it downloads the canonical template once from the public repo (`AVALERE_PPTX_TEMPLATE_URL`, default `raw.githubusercontent.com/.../wiki/skills/_assets/Avalere_PPT_template.potx`) and caches it under the temp dir. So two bundle shapes work:

- **Slim** (`velorixa-avalere-pptx-skill.zip`, ~10 KB): no template; the engine pulls it from the public repo at first build, so it is always current and never drifts. Needs the sandbox to allow outbound network to `raw.githubusercontent.com`.
- **Offline** (`velorixa-avalere-pptx-skill-offline.zip`, ~3.5 MB): ships the template under `assets/`; works with no network. Use this if code execution blocks egress.

Either way the output is on-brand because the bytes are the same pinned template.

## How to build

1. Read the relevant wiki pages (project, entities, concepts, sources) and gather the content and its source IDs. Every claim on a slide must trace to a source.
2. Decide a slide sequence and map each slide's intent to the closest-named layout. Read layout names with `python3 build_deck.py list-layouts`. Families: Cover (Pink, Turquoise/Lime, Cutout, Custom), Title and Content (White, Black, Pink, Turquoise/Lime, plus Corner Gradient, Slash, Wide Slash), Manifesto/Intro, Divider, Agenda, 2/3/4 Headered Columns, 6 Text Sections, Half Split, Third Split, Aframe Split, RHS/Bottom Stats Panels, Timeline, Team of 5/10/15/24, Large Statement, Case Study, Thank You, Title only, Blank.
3. **Inspect the chosen layout's slots** so you can fill all of them: `python3 build_deck.py describe-layout "<layout name>"`. It lists every fillable placeholder with its `idx`, role, and a `hint` (the layout's own prompt text, for example `##%` marks a stat figure). Slots are listed in document order, normally left-to-right then top-to-bottom.
4. Write a spec JSON (see `sample_spec.json`) with the deck title and a `slides` list. Layout matching is dash and case insensitive. Each slide:
   ```jsonc
   {
     "layout": "3 Headered Columns - White",
     "title": "Slide title",
     "citations": ["src-id"],            // optional, also accepted per placeholder
     "notes": "speaker notes",           // optional
     // Simple layouts: a single body.
     "subtitle": "optional subheading",
     "bullets": ["point", "point"],
     // Rich layouts: fill every slot from describe-layout, by idx.
     "placeholders": [
       {"idx": 12, "text": "one-line subheading"},
       {"idx": 26, "paragraphs": [
          {"text": "Column header", "level": 0},
          {"text": "supporting point", "level": 1},
          {"text": "supporting point", "level": 1}
       ]},
       {"idx": 30, "paragraphs": ["..."], "citations": ["src-id"]}
     ]
   }
   ```
   A paragraph is a plain string, or `{"text": ..., "level": N}` for indented sub-bullets. `placeholders` and the simple `subtitle`/`bullets` can coexist; the engine never double-fills a slot.
5. Run the engine:
   ```
   python3 build_deck.py <spec.json> --out <output.pptx>
   ```
   It opens the template, clears the template's demo slides while keeping all masters, layouts, and theme, adds a slide per spec entry on the chosen layout, fills the title and every targeted placeholder, renders citations inline as `[src:id]`, and writes source IDs into the slide notes.
6. File a completion record back into the wiki: create a source-adjacent note under `synthesis/` or append to the project page recording the deck generated, the layouts used, and every source ID cited. Append a line to `log.md`.

## Make slides rich, not sparse

The most common quality failure is an on-brand deck that is half-empty: a title and three bullets sitting on a layout built to hold far more. The template gives the brand; you supply rich, well-structured content for every slot. Compose with the same care you would a freehand deck, then express it through the template. So:

- **Be specific, not vague.** Pull the concrete detail from the sources: actual names and roles, exact phrases, real figures, the named decision and who made it. "Discussed prohibited claims" is weak; "Prohibited: cure, guaranteed sleep, next-day effect, 'reset your brain'" is strong. Specific content is what makes a deck feel authoritative, and it is the single biggest difference between a thin deck and a great one.
- **Choose layouts that match the content's shape.** Reach for the content-rich layouts (2/3/4 Headered Columns, RHS/Bottom Stats Panels, 6 Text Sections, Half/Third/Aframe Splits, Timeline, Case Study, Agenda Expanded) when the material suits them, rather than defaulting every slide to plain Title and Content.
- **Fill every slot.** Run `describe-layout` for the chosen layout and write one `placeholders` entry per `idx` it lists. Do not leave columns, sections, or stat figures empty. An empty column is the tell-tale sign of a thin deck.
- **Use structure inside a slot.** Give each box a short header paragraph (`level` 0) and a few supporting points (`level` 1) rather than one flat line.
- **Aim for the density of a strong hand-made deck.** Enough slides to tell the story, each slot carrying a real, sourced point. This is how the on-brand output matches the quality of a freehand deck instead of looking flat.

## Rules

- Theme, fonts, and layout geometry come from the template. Do not set ad-hoc colours or fonts; let the layout carry the brand.
- Provenance is mandatory. A slide with an uncited factual claim is not allowed. If a claim cannot be sourced, drop it or flag for review.
- Sensitivity inherits from the project and its cited sources. A deck citing a confidential source is confidential and follows the gating rules in `../../CLAUDE.md`.
- This skill is authored for the Velorixa tenant. It is not reusable in another tenant without review and reauthoring.
