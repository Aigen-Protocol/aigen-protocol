# How to push the pending commits to github.com/Aigen-Protocol/aigen-protocol

**Status:** 5 local commits ahead of `origin/main` are blocked because the
current GitHub OAuth token (account: `Pandiums`) lacks the `workflow` scope.

```
$ gh auth status
✓ Logged in to github.com account Pandiums
- Token scopes: 'gist', 'read:org', 'repo'
                                       ↑ no `workflow`
```

A previous commit (`348c99a` — "Add GitHub Actions health check (every 6h)")
modifies `.github/workflows/health-check.yml`. Pushing any commit that touches
a workflow file requires the `workflow` scope.

## Option 1 — refresh scope (recommended)

```bash
gh auth refresh -h github.com -s workflow
```

This opens a browser window for the device-code flow. After approving:

```bash
cd /home/luna/crypto-genesis/aigen
git push origin main
```

Should land all 5 commits (audit, weekly report, /watch, /saferouter,
saferouter demo).

## Option 2 — Personal Access Token with workflow scope

If `gh auth refresh` is awkward, create a fine-grained PAT at
https://github.com/settings/tokens/new with:
- repo: write
- workflow: write

Then:

```bash
cd /home/luna/crypto-genesis/aigen
git push https://<USERNAME>:<PAT>@github.com/Aigen-Protocol/aigen-protocol.git main
```

## Option 3 — push without workflow file changes (last resort)

Cherry-pick everything except `348c99a` onto a new branch and push that.
Discouraged because it splits history.

```bash
git checkout -b main-no-workflow origin/main
git cherry-pick 8949083 54aacec 4191962 afa7a0f facf228 a53e84b 1b03821 e129066 d9d133f 3511361 bf89a8a 9a54317 e3aaaeb 17a74b2 119b5b4 f96fb8c d5b7027 9333130 0ecd746 abd365a 5e230e1 4b9f39c f19fc89 3c2cb8b
git push origin main-no-workflow
# then PR-merge into main from GitHub UI
```

## After push succeeds

The 5 most recent commits expose the new infrastructure publicly:

| Commit | What it adds |
|---|---|
| `0ecd746` | Audit (rejected 14 fake submissions, anti-spam validator) |
| `abd365a` + `5e230e1` | Weekly W19 safety report + chat post |
| `4b9f39c` | `/watch` endpoint + signed webhooks |
| `f19fc89` | SafeRouter on-chain activated, oracle updater |
| `3c2cb8b` | First swap demo + V2 issue note |

Once pushed, the Smithery / Cline / Igor distribution drafts (in
`/distribution/`) can cite the public GitHub URLs.
