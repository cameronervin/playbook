# Documentation Coverage Checklist

Use this checklist to verify documentation completeness.

## Core Documentation

### AGENTS.md
- [ ] First Principles section is accurate
- [ ] Architecture diagram matches actual code structure
- [ ] Boundaries table is current
- [ ] Libraries table reflects actual dependencies
- [ ] Documentation folder structure matches reality
- [ ] PRD folder structure matches reality
- [ ] Implementation folder structure matches reality
- [ ] Rules table references correct files
- [ ] Commands section has working examples

### docs/architecture/
- [ ] `overview.md` - System diagram is current
- [ ] `overview.md` - Layer descriptions are accurate
- [ ] `db.md` - Database schema matches models
- [ ] `decisions/` - ADRs exist for major decisions
- [ ] `decisions/` - ADRs are not contradicted by code

### docs/api/
- [ ] `endpoints.md` - All endpoints documented
- [ ] `endpoints.md` - Request/response schemas accurate
- [ ] `endpoints.md` - Error responses documented

### docs/guides/
- [ ] `setup.md` - Local setup instructions work
- [ ] `setup.md` - Dependencies are correct versions
- [ ] `deployment.md` - Deploy instructions are current
- [ ] `contributing.md` - Contribution process is accurate
- [ ] `postgresql_setup.md` - PostgreSQL setup works
- [ ] `localstack_setup.md` - LocalStack setup works

### docs/agents/
- [ ] `tools.md` - All tools documented
- [ ] `tools.md` - Tool signatures are accurate
- [ ] `context-engineering.md` - Context engineering guidance is current

## Product Documentation

### prd/
- [ ] `01-user-stories/` - User stories are complete
- [ ] `02-technical-docs/` - Technical specs match implementation
- [ ] `02-technical-docs/api-specification.md` - API spec matches endpoints.md

### prd/03-implementation/
- [ ] Current phase file reflects actual progress
- [ ] `_implementation-plan.md` - Gap analysis is accurate
- [ ] Completed phases are marked correctly

## Code-to-Doc Alignment

### Backend
- [ ] Every endpoint in `api/v1/` has API documentation
- [ ] Every service has docstrings explaining purpose
- [ ] Every repository has docstrings explaining data access
- [ ] Complex algorithms have inline comments
- [ ] Error codes are documented

### Frontend
- [ ] Component props are documented (TypeScript types)
- [ ] Complex hooks have usage examples
- [ ] State management is documented
- [ ] API integration is documented

## Freshness Indicators

Check last modified dates:

| File | Max Age | Check |
|------|---------|-------|
| `docs/api/endpoints.md` | 30 days | After any API change |
| `docs/guides/setup.md` | 60 days | After dependency updates |
| `AGENTS.md` | 30 days | After structure changes |
| `implementation/remaining-work.md` | 7 days | Weekly update |
| `docs/architecture/decisions/` | N/A | Decisions don't expire |

## Cross-Reference Checks

### Internal Links
- [ ] All `[text](path.md)` links resolve
- [ ] All `@file` references in AGENTS.md exist
- [ ] All relative paths are correct

### External References
- [ ] External documentation links are valid
- [ ] Library documentation links are to current versions
- [ ] No dead links to deprecated resources

## Common Issues

| Issue | How to Detect | How to Fix |
|-------|--------------|------------|
| Undocumented endpoint | `rg "@router" api/` vs endpoints.md | Add endpoint documentation |
| Stale setup guide | Try following the guide | Update with current steps |
| Missing ADR | Major decision without docs | Create new ADR |
| Broken link | Click all links / automated checker | Fix or remove link |
| Outdated diagram | Compare to actual code | Regenerate diagram |
| Wrong folder structure | `ls` vs AGENTS.md | Update AGENTS.md |
