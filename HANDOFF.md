# HANDOFF

## Current Work

### Goal
Fix and verify the GitHub Actions automated data refresh workflow for the fintel stock analysis application.

### Context
- **Project**: fintel - a stock analysis dashboard with S&P 500 data, picks, news, and market indicators
- **Stack**: Python backend (orchestration pipeline), Astro frontend with React components
- **Data flow**: Python pipeline fetches stock data → generates `frontend/src/data/report.json` → Astro serves it

### Progress

| Task | Status |
|------|--------|
| Run local data refresh | complete |
| Investigate why auto-refresh didn't run at market open | complete |
| Fix missing `requirements.txt` | complete |
| Fix Python version (3.11 → 3.12 for PEP 695 syntax) | complete |
| Fix workflow push permissions (`contents: write`) | complete |
| Update schedule to market open/close | complete |
| Manually trigger and verify workflow succeeds | complete |
| Check site with new data | complete |

### Decisions Made

1. **Scheduling mechanism**: GitHub Actions (runs on GitHub servers, user's computer can be off)
2. **Schedule times**:
   - Market open: 9:30 AM ET → `cron: '30 14 * * 1-5'` (14:30 UTC)
   - Market close: 4:00 PM ET → `cron: '0 21 * * 1-5'` (21:00 UTC)
   - Weekdays only (Mon-Fri)
3. **Python version**: 3.12 required (code uses PEP 695 type parameter syntax: `def foo[T: BaseModel](...)`)

### Key Files Modified

| File | Change |
|------|--------|
| `requirements.txt` | Created from venv (was missing entirely) |
| `.github/workflows/refresh-data.yml` | Python 3.11→3.12, added `permissions: contents: write`, updated cron schedule |

### Commits This Session
```
61fcf66 chore: add requirements.txt for GitHub Actions
0561129 chore: schedule data refresh at market open and close
b33d806 fix: use Python 3.12 for PEP 695 type syntax
588bf89 fix: grant write permissions to workflow for auto-commit
f91b7a0 chore: refresh market data [skip ci] (auto-committed by workflow)
```

### Next Steps
1. **Check the site** - verify the new data displays correctly on http://localhost:4321
   - Dev server was running on port 4321 (background task b39b6cb)
   - May need to restart if stale
2. **Optional**: Add error notifications to workflow (currently silent on success/failure)

### Blockers
None - workflow is fully operational.

---

## History
- 0d06ebd: initial commit with all code
- 08d91e0: redesign UI with CNN Business aesthetic
- 38e14bf: refresh market data with latest prices
- 77adbfd: add auto-refresh scheduling for data pipeline (had bugs fixed this session)
- 10f765a: add market cap to LiteStock for proper heatmap sizing

---

## Anti-Patterns

### 1. Missing `requirements.txt` for GitHub Actions
**Symptom**: Workflow failed with `ERROR: Could not open requirements file: [Errno 2] No such file or directory: 'requirements.txt'`

**Root cause**: When creating the workflow file, assumed `requirements.txt` existed. Project was managing dependencies only in venv without a manifest file.

**Resolution**: Generate from venv: `.venv/bin/pip freeze > requirements.txt`

**Prevention**: Always verify dependency files exist before referencing in CI.

---

### 2. Python version mismatch (PEP 695 syntax)
**Symptom**: `SyntaxError: expected '('` on line with `def from_json_dict[T: BaseModel](...)`

**Root cause**: Code uses Python 3.12+ type parameter syntax (PEP 695), but workflow used Python 3.11.

**Resolution**: Update workflow to use `python-version: '3.12'`

**Prevention**: Match CI Python version to local development version. Check for modern syntax usage.

---

### 3. GitHub Actions push permission denied
**Symptom**: `remote: Permission to repo.git denied to github-actions[bot]. fatal: unable to access ... 403`

**Root cause**: Default `GITHUB_TOKEN` doesn't have write permissions unless explicitly granted.

**Resolution**: Add to workflow:
```yaml
permissions:
  contents: write
```

**Prevention**: Any workflow that commits/pushes needs explicit `contents: write` permission.

---

## Anti-Pattern Cache
| Hash | Pattern | Resolution |
|------|---------|------------|
| 61fcf66 | missing requirements.txt | `git show 61fcf66` - created file |
| b33d806 | Python 3.11 vs 3.12 | `git show b33d806` - version bump |
| 588bf89 | push permissions | `git show 588bf89` - added permissions block |
