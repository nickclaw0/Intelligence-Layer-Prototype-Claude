# Daily lint (Phase 6)

The scheduled maintainer for the Velorixa Intelligence Layer. It runs once a day as a Claude routine (Claude stack) and folds in only what is new or changed since the last run.

## The hard rule

It must not rewrite the wiki. It is a diff against state, not a sweep. The manifest's content hashes are the source of truth for what changed. Unrelated pages are left byte-for-byte unchanged. If a run finds nothing new, it appends a single "no changes" line to `log.md` and exits.

## What a run does

1. Diff the raw manifest's content hashes against `lint/.lint_state.json`.
2. For only the new or changed source ids: ensure a source page exists (create a `needs-synthesis` stub if the maintainer has not authored one yet), and ensure a one-line entry exists in the index Sources section.
3. Run the schema's lint checks over the affected neighbourhood only: broken citations (a cited id missing from the manifest), orphan pages (no inbound WikiLink), and contradictions. Contradictions are surfaced for human review, never resolved silently. Broken citations exit non-zero so the run can gate.
4. Append exactly one lint summary line to `log.md` and update the state.

## Run it

```
python3 lint/daily_lint.py
python3 lint/daily_lint.py --manifest "/path/to/raw/_manifest.json" --repo /path/to/repo
```

The manifest path defaults to the Drive raw manifest and can be overridden with `--manifest` or the `RAW_MANIFEST` environment variable.

## State

`lint/.lint_state.json` holds the last lint timestamp and the last-seen content hash per source id. It is per-environment runtime state and is gitignored; the scheduled routine persists its own. A fresh state simply re-folds existing sources on the first run (idempotent: it never edits a source page that already exists, it only ensures the page and index entry are present).

## Schedule it

See `routine.md` for the once-a-day Claude routine definition. Activate it with the `/schedule` skill (Claude routine) or a cron entry. Activation is left to the human so the schedule is created deliberately.

## Scope boundary

The daily job stays cheap and additive. The monthly-grade work (a full orphan sweep across the whole wiki, stale-claim review, and an index health check) is a separate, less frequent routine and is deliberately not part of this daily job.
