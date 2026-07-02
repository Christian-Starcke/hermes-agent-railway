# Smoke test and cutover checklist

Run after deploying Paperclip and updating Hermes with the `paperclip` plugin.

## 1. Unit tests (local / CI)

```bash
cd .work/hermes-agent-railway/plugins/paperclip
python -m unittest test_paperclip.py -v
```

## 2. Paperclip service health

From Railway Hermes `/tui` or any shell with env vars:

```bash
curl -s -H "Authorization: Bearer $PAPERCLIP_API_TOKEN" \
  "$PAPERCLIP_BASE_URL/api/health"
```

## 3. Hermes plugin smoke (live API)

```bash
python3 /data/.hermes/plugins/paperclip/smoke_test_local.py
```

Optional delegation (creates a real issue):

```bash
PAPERCLIP_SMOKE_DELEGATE=1 \
PAPERCLIP_DEFAULT_REPOSITORY=owner/repo \
python3 /data/.hermes/plugins/paperclip/smoke_test_local.py
```

## 4. Hermes WebUI chat E2E

1. Set `PAPERCLIP_DELEGATION_MODE=paperclip` on Hermes and redeploy.
2. Start a **new** WebUI session with `paperclip` toolset enabled.
3. Prompt:

   > Delegate a trivial doc fix in `owner/repo` via Paperclip. Do not merge.

4. Confirm Hermes returns a `PAP-xx` issue id (not a Cursor `bc-` agent id).
5. Open Paperclip UI — issue should appear as `todo` then `in_progress`.
6. After worker completes, ask Hermes: `Status on PAP-xx?` — should report PR/branch from issue.

## 5. Cutover

| Step | Action |
|------|--------|
| Before | `PAPERCLIP_DELEGATION_MODE` unset → direct Cursor via `cursor-delegate` |
| Cutover | Set `PAPERCLIP_DELEGATION_MODE=paperclip`, redeploy Hermes |
| Verify | `cursor-cloud` disabled in `/data/config.yaml` plugins.enabled |
| Fallback | Set mode back to `direct` and redeploy to re-enable `cursor-cloud` |

## 6. Optional: remove Hermes Cursor cron

When on Paperclip mode, the `/data/cron/cursor-cloud-poll.sh` cron job is no longer needed for delegated work. Paperclip heartbeats poll Cursor.
