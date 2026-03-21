## Summary

<!-- 1-3 bullet points: what changed and why -->

-

## Type of change

- [ ] `feat` — new feature
- [ ] `fix` — bug fix
- [ ] `security` — security fix
- [ ] `refactor` — code cleanup, no behaviour change
- [ ] `test` — test-only changes
- [ ] `docs` — documentation only
- [ ] `chore` — tooling, deps, CI

## Test plan

- [ ] `SKIP_SECURITY_CHECKS=1 uv run pytest` passes locally
- [ ] New service-layer tests written (required for `feat` and `fix`)
- [ ] Coverage still ≥ 80% on `app/services/`

## Checklist

- [ ] `CHANGELOG.md` updated under `[Unreleased]`
- [ ] DB migration created and tested (if schema changes)
- [ ] All new HTML `POST` routes have `Depends(require_csrf)`
- [ ] No secrets rendered into templates
- [ ] No business logic added to routers
