---
name: skill-creator
description: Draft, lint, and propose new skills, enforcing the client-portability rule
triggers:
  - query_patterns: ["create a skill", "new skill", "scaffold a skill", "lint skills"]
  - event: new_skill_requested
required_tools:
  - file_read
  - file_creation
  - code_execution
inputs:
  - skill_name: string
outputs:
  - SKILL.md
sensitivity: internal
client: velorixa
---

The meta-skill that knows how to make other skills. It scaffolds a well-formed SKILL.md, lints existing skills for structure, and enforces that every skill is tenant-scoped.

## Engine

`skill_creator.py`.

```
python3 skill_creator.py scaffold <skill-name> --client velorixa --desc "what it does"
python3 skill_creator.py lint <skill-name|all>
```

- **scaffold** creates `skills/<name>/SKILL.md` from the standard frontmatter-plus-body template, pre-stamped with the client and the portability statement. Fill in the TODOs, then run `lint` and the `skill-test` skill.
- **lint** checks every skill has the required frontmatter keys (`name`, `description`, `triggers`, `required_tools`, `inputs`, `outputs`, `sensitivity`, `client`) and that the body carries the client-portability statement.

## The client-portability rule

A skill built for one tenant is not reusable in another tenant without explicit review and reauthoring. Every skill carries a `client` field and a statement to that effect in its body. The lint fails any skill that drops either. This keeps the client firewall intact at the skill layer.

## Rules

- New skills follow the structure in the existing skills (frontmatter, base assets, how-to-build steps, rules).
- A skill is only catalogued in `index.md` after it passes both `skill-creator lint` and `skill-test`.
