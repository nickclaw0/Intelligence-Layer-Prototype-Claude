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
  # Optional: keep the live viewer in sync with the wiki. When VIEWER_AUTODEPLOY
  # is truthy and CF_API_TOKEN is present, a run that changed the wiki rebuilds
  # worker.js and redeploys the Cloudflare Worker (viewer/deploy_viewer.py). The
  # Basic-Auth secrets are preserved via inherit bindings, so only the API token
  # is needed. Omit these and the lint behaves exactly as before (no deploy).
  VIEWER_AUTODEPLOY: "1"
  CF_API_TOKEN: "<cloudflare token with Workers Scripts:Edit>"   # secret; inject from the routine's secret store, never commit
on_nonzero_exit: notify        # broken citations exit 2; surface to a human
```

## Keeping the viewer in sync

The viewer is a static bake (node-free; the wiki lives in a private repo the
Worker cannot read at request time), so "the graph always reflects the wiki"
means rebuild + redeploy on change. The daily lint does this automatically when
`VIEWER_AUTODEPLOY` + `CF_API_TOKEN` are set; a deploy failure is reported in the
log line but never fails the lint. To resync by hand at any time:

```
CF_API_TOKEN=... python3 viewer/deploy_viewer.py
```

## Agent prompt (if run as a reasoning routine rather than a bare script)

> Read `wiki/CLAUDE.md` for the lint protocol, then run `python3 lint/daily_lint.py`. The script folds in only new or changed raw sources since the last run, ensures their source pages and index entries exist, and runs scoped lint checks. Do not rewrite unrelated pages. If the run reports broken citations or surfaces a contradiction, do not auto-resolve: open a human-review note summarising what was found and stop. Otherwise confirm the single log line the script appended is accurate.

## Activation

Create it with the `/schedule` skill (Claude routine) or an equivalent cron entry. The human activates it deliberately. The separate monthly sweep (full orphan/stale/index-health pass) is its own routine and is not defined here.

## Current deployment

Created as a **remote Claude routine** (runs in Anthropic's cloud, not on a local
machine): name `velorixa-daily-lint`, id `trig_014bDabKh7nT66xBbvPbJhVH`,
schedule `0 5 * * *` (06:00 Europe/London = 05:00 UTC), env NateClaw, model
`claude-sonnet-4-6`, source repo `nickclaw0/Intelligence-Layer-Prototype-Claude`.
Manage at `https://claude.ai/code/routines/trig_014bDabKh7nT66xBbvPbJhVH`.

Two consequences of it being remote, both reflected in the routine's prompt:

- **Manifest access.** The cloud env cannot see the local Drive mount, so the
  routine fetches `raw/_manifest.json` through the attached Google Drive
  connector and runs `daily_lint.py --manifest <downloaded copy>`.
- **No viewer redeploy.** There is no Cloudflare token in the cloud env, so the
  routine does not run `viewer/deploy_viewer.py`. It folds sources and pushes to
  GitHub; the viewer is resynced separately (locally).

**Open blocker:** a verification run returned `github_repo_access_denied`. The
Claude GitHub App must be re-authorized for the repo on the NateClaw environment
before the routine can clone it; until then each fire fails the same way. After
re-authorizing, trigger a run to confirm the full chain (Drive manifest -> lint
-> commit/push).
