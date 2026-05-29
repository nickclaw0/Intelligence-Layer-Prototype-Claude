# Index — Velorixa Intelligence Layer

The catalogue of the wiki, sectioned by page type. Read this first on every query. Each entry is one line: link, one-sentence summary, and optional metadata. Updated on every ingest.

Tenant: Velorixa (VLX), insomnia, project launch-prep. Schema: [CLAUDE.md](CLAUDE.md), version 1.0.0.

## Entities

_None yet._

## Concepts

_None yet._

## Sources

- [[sources/2026-04-02-kickoff-brand-ambition]] — Brand strategy kickoff: ambition, positioning direction, claims guardrails, proposal shape, research approach. (transcript, 1 source, 2026-04-02)
- [[sources/2026-04-09-positioning-workshop]] — positioning workshop (transcript, 1 source)

## Projects

_None yet._

## Synthesis

- [[synthesis/2026-05-29-velorixa-sample-outputs]] — Completion record for the first run of the Avalere deck and document skills, generated from the kickoff source. (1 source)

## Decisions

_None yet._

## Skills

Skills are first-class nodes in the wiki graph and can be linked from entity, concept, and project pages. A project page's `available_skills` list surfaces them as invocable actions in the viewer.

- [[skills/generate-avalere-pptx/SKILL]] — Build an on-brand PowerPoint deck in the Avalere Health 2025 template, content and citations pulled from the wiki. (template-as-base, 132 named layouts)
- [[skills/generate-avalere-docx/SKILL]] — Build an on-brand Word document in the Avalere template, using its named styles, header, footer, and logo. (template-as-base)
- [[skills/provenance-export/SKILL]] — Export every claim, source, and inherited sensitivity for an output so a compliance reviewer can verify it.
- [[skills/skill-creator/SKILL]] — Meta-skill: scaffold, lint, and propose new skills, enforcing the client-portability rule.
- [[skills/skill-test/SKILL]] — Run a skill against a known input and check its output structure before commit.
