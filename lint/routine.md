# Claude routine: daily-lint

A once-a-day scheduled agent that maintains the Velorixa Intelligence Layer wiki incrementally.

## Definition

```yaml
name: velorixa-daily-lint
schedule: "0 6 * * *"          # 06:00 daily
stack: claude
working_dir: <repo root>
command: python3 lint/daily_lint.py
env:
  RAW_MANIFEST: "/path/to/Intelligence Layer Prototype_Claude_v1/raw/_manifest.json"
on_nonzero_exit: notify        # broken citations exit 2; surface to a human
```

## Agent prompt (if run as a reasoning routine rather than a bare script)

> Read `wiki/CLAUDE.md` for the lint protocol, then run `python3 lint/daily_lint.py`. The script folds in only new or changed raw sources since the last run, ensures their source pages and index entries exist, and runs scoped lint checks. Do not rewrite unrelated pages. If the run reports broken citations or surfaces a contradiction, do not auto-resolve: open a human-review note summarising what was found and stop. Otherwise confirm the single log line the script appended is accurate.

## Activation

Create it with the `/schedule` skill (Claude routine) or an equivalent cron entry. The human activates it deliberately. The separate monthly sweep (full orphan/stale/index-health pass) is its own routine and is not defined here.
