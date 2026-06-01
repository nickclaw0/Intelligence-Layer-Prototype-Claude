---
name: velorixa-intelligence-layer
description: Query the Velorixa Intelligence Layer wiki (Layer 1) with provenance, sensitivity gating, and tenant scope, using the GitHub and Google Drive connectors, and produce on-brand Avalere PowerPoint/Word deliverables by pulling the Avalere generator and its pinned template from the wiki git. This is the only skill to install; it never uses a generic deck or document maker. Cite every claim. Refuse cross-tenant requests.
triggers:
  - query_patterns: ["velorixa", "VLX", "the intelligence layer", "the wiki", "what did we decide", "what does the wiki say", "build a deck", "make a deck", "create a deck", "deck about", "make a presentation", "presentation about", "powerpoint", "power point", "ppt", "pptx", "slide deck", "slides for", "avalere deck", "write a document", "word doc", "word document", "docx", "one-pager", "one pager", "recap document", "write-up", "brief"]
required_connectors:
  - github
  - google_drive
client: velorixa
sensitivity: inherits_from_wiki
---

# Velorixa Intelligence Layer access skill

This skill lets you query the Velorixa Intelligence Layer wiki (Layer 1, in GitHub), drop to its raw sources (Layer 0, in Google Drive) when needed, and produce on-brand Avalere PowerPoint and Word deliverables by pulling the Avalere generator engine and its pinned template straight from the wiki git and running them in code execution. It is the browser-installable, connector-based variant of `access-skill/`. Same rules, same cascade, different transport.

**This is the only skill you install on Claude.ai.** Everything else it needs, including the Avalere PowerPoint and Word generators, it fetches from the wiki git at the moment it is needed. Do not install a separate deck or document skill, and never fall back to a generic or built-in PowerPoint/Word maker. Branded deliverables come only from the Avalere engine in the wiki git.

The schema at `wiki/CLAUDE.md` is the highest-weight document in the system. Load it at session start and follow it verbatim. When this skill body and the loaded schema disagree, the schema wins.

## Where things live

- **Wiki (Layer 1)**: GitHub repo `nickclaw0/Intelligence-Layer-Prototype-Claude`, branch `main`. Read with the **GitHub connector**.
- **Raw (Layer 0) and the manifest**: the Google Drive folder named `Intelligence Layer Prototype_Claude_v1`, specifically the `raw/` subtree. The manifest is at `raw/_manifest.json`. Read with the **Google Drive connector**.

If either connector is missing or returns nothing, stop and report which one. Do not guess and do not answer from general knowledge.

## Connectors and their tools

This skill runs on two connectors. Call them by name and use the specific operations below.

### GitHub connector (the wiki, Layer 1)

Owner `nickclaw0`, repo `Intelligence-Layer-Prototype-Claude`, branch `main`.

- **Read a file**: the GitHub connector's file-contents tool (commonly named `get_file_contents`). Pass `owner = nickclaw0`, `repo = Intelligence-Layer-Prototype-Claude`, and a `path` such as `wiki/CLAUDE.md`, `wiki/index.md`, or `wiki/sources/<slug>.md`.
- **Search the repo**: the GitHub connector's code-search tool (commonly named `search_code`), scoped to `repo:nickclaw0/Intelligence-Layer-Prototype-Claude`, to find pages that mention a term.

If the GitHub connector is not present in the session, stop and tell the user it must be added and enabled before the skill can work. The entire wiki lives on GitHub, so without this connector there is nothing to ground answers in. Do not substitute general knowledge.

### Google Drive connector (raw, Layer 0)

The `Intelligence Layer Prototype_Claude_v1` folder, `raw/` subtree.

- **Find a file**: `search_files` with a structured query. Examples:
  - `title contains '_manifest'` to find the manifest.
  - `fullText contains '<slug>'` or `title contains '<basename>'` to find a raw source by name.
  - Narrow to the project with `parentId = '<folder id>'` once a folder id is known.
- **Read a file**: `read_file_content` with the `fileId` returned by `search_files`.

Drive limitation to respect: `read_file_content` supports Google Docs, Slides, Sheets, PDF, Word, Excel, PowerPoint, and images. It does **not** support plain `.txt`, `.md`, or `.json`. The raw transcripts and `_manifest.json` are plain text, so read them from the content snippets that `search_files` returns (call it with `excludeContentSnippets` unset or false). For a large raw file the snippet may be partial; say so rather than inventing the rest.

## The query cascade (run in order)

1. **Read the schema first.** Use the GitHub connector's file-contents tool to read `wiki/CLAUDE.md` from `nickclaw0/Intelligence-Layer-Prototype-Claude`. Apply its rules to everything that follows. If the GitHub connector is missing, stop and report it.
2. **Read the index.** Read `wiki/index.md` the same way. The index enumerates the wiki: entities, concepts, sources, projects, synthesis, decisions, skills.
3. **Identify candidate pages.** Pick the entity, concept, project, synthesis, and source pages the query touches. When the query word does not appear in the index, use the GitHub connector's code-search tool (`repo:nickclaw0/Intelligence-Layer-Prototype-Claude`) to find pages that reference it.
4. **Read the candidate pages.** Read each `wiki/<path>.md` with the GitHub connector's file-contents tool.
5. **Answer with citations.** Every factual claim in the response cites a source id, in the inline form `[claim]^[src:<id>]`. Source ids are the manifest keys (sha256 content hashes for now; Drive file ids once Phase 3 reconciles). Keep house style: plain and conversational, no em dashes, no "X is not just Y" construction, no forced three-item lists.
6. **Drop to raw only when the wiki summarises and points there**, or when the question demands detail the wiki does not carry. Procedure (Google Drive connector):
   1. Find the manifest with `search_files` (`title contains '_manifest'`) and read it from the returned content snippet.
   2. Find the manifest entry whose `id` (or `short_ref`) matches the citation.
   3. Confirm the entry's `client` field is `velorixa`. If it is anything else, refuse and stop. The tenant guard rejects cross-client access.
   4. Find the raw file by the basename of its `current_path` with `search_files` (`title contains '<basename>'`), then read it. For a plain-text source the content comes from the search snippet, since `read_file_content` does not support `.txt`. Integrate the original detail into the answer using the same `^[src:<id>]` citation.
7. **If the answer is non-trivial and likely reusable**, say so plainly so a human can decide whether to file it back as a synthesis page. Do not edit the wiki yourself.

Most queries resolve at step 5. Drop to raw only when needed.

## Producing a deck or document

When the request is for a PowerPoint, deck, slides, Word document, one-pager, or recap, the answer is a branded file, not prose, and it is built with the Avalere generator from the wiki git, run in code execution. You do not install a separate generator skill and you never use a generic or built-in deck/doc maker. This one skill pulls the Avalere engine and its pinned Avalere template from the public repo and runs them.

1. Run the cascade above to gather the content and, for every claim, its source id.
2. **Pull the Avalere engine from the wiki git** into the code-execution sandbox. Each engine is a single self-contained Python file (pure standard library, no installs):
   - PowerPoint: `wiki/skills/generate-avalere-pptx/build_deck.py`
   - Word: `wiki/skills/generate-avalere-docx/build_doc.py`

   Fetch the raw file from the public repo, for example:
   ```python
   import urllib.request
   base = "https://raw.githubusercontent.com/nickclaw0/Intelligence-Layer-Prototype-Claude/main/wiki/skills"
   urllib.request.urlretrieve(base + "/generate-avalere-pptx/build_deck.py", "build_deck.py")
   ```
   (or read the file with the GitHub connector's file-contents tool and write it out). Do not write your own renderer.
3. **Write a spec JSON** whose every factual claim carries a source id. The engine renders citations inline as `[src:id]`.
   - Doc spec: `{blocks:[{style, text, citations?}]}`.
   - Deck spec: `{title, slides:[{layout, title, citations?, notes?, ...content}]}`. For each slide, choose a layout (`python3 build_deck.py list-layouts`), then inspect its slots with `python3 build_deck.py describe-layout "<layout>"` and fill them. Simple layouts take `subtitle` and `bullets`. Rich layouts (columns, stats panels, sections, splits) take a `placeholders` list, one entry per `idx` from describe-layout: `{"idx": N, "text": "..."}` or `{"idx": N, "paragraphs": ["...", {"text": "...", "level": 1}]}`.
   - **Make the deck dense, not flat.** The number-one quality failure is an on-brand deck that comes out half-empty. Pick content-rich layouts where the material suits them, fill *every* slot describe-layout lists (no empty columns or stat boxes), give each box a short header plus supporting points, and use enough slides to tell the story. The template supplies the brand; you supply rich, sourced content for every slot, to the standard of a strong hand-made deck.
4. **Run the engine** in code execution:
   ```
   python3 build_deck.py spec.json --out deck.pptx
   python3 build_doc.py  spec.json --out document.docx
   ```
   On first run the engine fetches the pinned Avalere template from the same public repo and caches it, so the output is on-brand without any template bundled here. Return the resulting `.pptx` / `.docx`.
5. The output inherits the highest classification of any source it cites.

This path needs the sandbox to allow outbound network to `raw.githubusercontent.com` (to pull the engine and the template). The standalone generator skills still live in the wiki git (`wiki/skills/generate-avalere-pptx/` and `wiki/skills/generate-avalere-docx/`, with the pinned templates under `wiki/skills/_assets/`). If that egress is ever blocked, a maintainer can export an offline bundle from those folders (the engine plus its template) and install that instead; it is no longer pre-staged on Drive, where only this query skill lives. Either way the output uses the Avalere engine and the pinned Avalere template; never substitute a generic builder, and if the engine cannot be fetched or run, say so and stop rather than producing an off-brand file.

## Hard rules

These mirror `wiki/CLAUDE.md`. The schema you load at step 1 is authoritative.

- **Provenance is mandatory.** Every factual claim cites a source id with `[claim]^[src:<id>]`. If a claim cannot trace to a manifest entry, say so plainly. Do not fill the gap from general knowledge.
- **Single tenant.** This skill serves the Velorixa tenant only. Refuse any request that names another client, asks to compare across clients, or tries to blend tenants. Refuse any raw source whose manifest `client` is not `velorixa`.
- **Sensitivity gating.** Classifications are `public`, `internal`, `client-confidential`, `regulated`. Sensitivity propagates upward: a response inherits the highest classification of any source it cites. State the inherited classification when it is `client-confidential` or `regulated`. Never surface `regulated` material without explicit human approval recorded in `wiki/log.md`.
- **MLR escalation.** Anything medical, legal, or regulatory pauses for human review. Do not answer free-hand. Surface the question and stop.
- **Off-label and safety.** Never extrapolate beyond approved indications. Never invent efficacy claims. Never aggregate safety data without explicit human approval. When uncertain about a safety or claims question, escalate by default.
- **Contradictions.** If new material contradicts three or more existing sources, surface the contradiction for human review rather than resolving it.
- **Deliverables only via the Avalere generator from the wiki git.** A PowerPoint is produced solely by the Avalere PPT engine (`wiki/skills/generate-avalere-pptx/build_deck.py`), a Word document solely by the Avalere DOCX engine (`wiki/skills/generate-avalere-docx/build_doc.py`), each pulled from the public wiki repo and run in code execution. The engine self-fetches the pinned Avalere template from the same repo. Never hand-build a deck or document, never use a generic or built-in PowerPoint/Word generator, never fall back to an off-brand template, and never hand the content back in another format to sidestep the engine. You do not install a separate generator skill: this single skill fetches the engine and template from git when a deliverable is requested. If the sandbox blocks egress to `raw.githubusercontent.com`, the fallback is to export an offline bundle (engine + template) from the wiki git and install that instead; only this query skill is staged on Drive. This skill gathers the cited wiki content and feeds the engine a spec; if the engine cannot be fetched or run, say so and stop rather than improvising an off-brand file.
- **Read-only.** This skill never edits the wiki, the manifest, or any raw file. The maintainer agent (separate, on the repo) commits wiki changes.

## House style

Plain and conversational. No em dashes. Avoid the "X is not just Y" construction. Do not force three-item lists. Prefer the source's wording over heavy paraphrase. Attribute client statements to the client; keep agency voice and client voice clearly separated.

## Acceptance

The skill is correctly installed and behaving when, in a fresh chat:

1. It loads the GitHub connector, fetches `wiki/CLAUDE.md`, and follows the cascade.
2. It answers a wiki-supported question (for example, "what was the kickoff brand ambition?") with at least one `[claim]^[src:<id>]` citation, with no claim left uncited.
3. For a question that needs raw detail beyond the source page summary, it uses the Drive connector to fetch `raw/_manifest.json`, resolves the id, confirms the entry's `client` is `velorixa`, reads the file, and integrates the detail with the same citation.
4. It refuses a request that names another client, and refuses to downgrade a classification.
5. For a deck or document request it gathers cited content, pulls the Avalere engine from the wiki git (`build_deck.py` / `build_doc.py`), runs it in code execution to fetch the pinned template and render the file, and returns an on-brand `.pptx` / `.docx` with citations as `[src:id]` — never a generic or hand-built file, and with no separate generator skill installed.

## Not in scope for v1

- **A generic or hand-built deck/doc.** This skill never renders a deliverable with a generic or built-in tool, and never asks you to install a separate generator skill. Branded PPTX/DOCX comes only from the Avalere engine pulled from the wiki git (`build_deck.py` / `build_doc.py`), run in code execution, which self-fetches the pinned Avalere template. This skill gathers and cites the content and feeds the engine a spec; it never improvises an off-brand file. Under the local stdio MCP variant in `access-skill/`, the same engines are exposed as the `generate_deck` / `generate_doc` tools.
- Wiki edits. Filing synthesis back is the maintainer's job, not this skill's.
