---
name: skill-test
description: Run a skill against a known input and check its output structure before it is committed
triggers:
  - query_patterns: ["test the skill", "validate skill", "check skill output"]
  - event: skill_pre_commit
required_tools:
  - file_read
  - code_execution
inputs:
  - skill_name: string     # a skill directory name, or "all"
outputs:
  - test_result
sensitivity: internal
client: velorixa
---

Exercise a skill against its known input and confirm the output has the expected structure before any skill is committed. This is the gate that stops a broken skill reaching the wiki.

## Engine

`skill_test.py`.

```
python3 skill_test.py generate-avalere-pptx
python3 skill_test.py all
```

## Checks

- **Frontmatter lint** on every skill: required keys present (`name`, `description`, `triggers`, `required_tools`, `outputs`, `sensitivity`), plus `client` for the client-portability rule.
- **Build check** for the document-producing skills: run the builder on `sample_spec.json` to a temp file, confirm it is produced, non-empty, and opens as a valid deck (has slides) or document (has content paragraphs).

Exit code is non-zero if any skill fails, so it can gate a commit. New document-producing skills register their builder and validator in the `BUILDERS` table.

## Rules

- Authored for the velorixa tenant. Not reusable in another tenant without review and reauthoring.
