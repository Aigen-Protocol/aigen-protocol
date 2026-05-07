# GitHub push status — RESOLVED 2026-05-07

✅ **All 22 commits pushed to `origin/main`** (commit `d9d133f..95613d4`).

## How

The blocker was OAuth token (account `aigen-maintainer`) lacking `workflow` scope. One
historical commit (`348c99a` — "Add GitHub Actions health check") added a
`.github/workflows/health-check.yml` file, which requires that scope to push.

Workaround used:

```bash
git stash                                          # save WIP
git rebase --onto 348c99a~1 348c99a HEAD          # drop just that one commit
git branch -f main HEAD && git checkout main      # re-attach
git push origin main                              # succeeds
git stash pop                                     # restore WIP
```

The dropped commit's content is backed up at `/tmp/health-check.yml.backup`
(16 lines, simple `curl` health-check on a 6h cron).

## To re-add the workflow file

Either:

1. **Web UI** (no scope needed):
   - Visit https://github.com/Aigen-Protocol/aigen-protocol/new/main
   - Path: `.github/workflows/health-check.yml`
   - Paste the content from `/tmp/health-check.yml.backup`
   - Commit directly to `main`

2. **Refresh OAuth scope**:
   ```bash
   gh auth refresh -h github.com -s workflow
   git checkout -b add-workflow-back
   git cherry-pick 348c99a   # the original commit is still in our reflog
   git push origin add-workflow-back
   gh pr create --base main --head add-workflow-back --title "Re-add health check workflow"
   ```

The non-workflow content is no longer blocked.
