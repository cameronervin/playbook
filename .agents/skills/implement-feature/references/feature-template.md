# Feature Execution Plan Template

Use this template for complex features (3+ files, cross-cutting concerns, multiple phases).

---

## Feature: [Name]

**User Stories:** US-XX, TS-XX  
**Owner:** [Name]  
**Created:** [Date]  
**Status:** Planning | In Progress | Complete

---

## Goal

[1-2 sentence description of what this feature accomplishes]

## Success Criteria

- [ ] [Concrete, verifiable outcome 1]
- [ ] [Concrete, verifiable outcome 2]
- [ ] [Concrete, verifiable outcome 3]

---

## Implementation Steps

### Step 1: [Name]

**Layer:** [api/v1 | services | repositories | models | frontend]  
**Files:**
- `path/to/file.py` - [What to create/modify]

**Test:**
- `test_step_1_behavior` - [What the test verifies]

**Dependencies:** None | Step X

---

### Step 2: [Name]

**Layer:** [api/v1 | services | repositories | models | frontend]  
**Files:**
- `path/to/file.py` - [What to create/modify]

**Test:**
- `test_step_2_behavior` - [What the test verifies]

**Dependencies:** Step 1

---

### Step 3: [Name]

[Continue pattern...]

---

## Decision Log

Track decisions made during implementation:

| Date | Decision | Rationale | Alternatives Considered |
|------|----------|-----------|------------------------|
| [Date] | [What was decided] | [Why] | [Other options] |

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| [Risk description] | High/Medium/Low | [How to address] |

---

## Progress Tracking

| Step | Status | Notes |
|------|--------|-------|
| Step 1 | [ ] Pending / [x] Complete | |
| Step 2 | [ ] Pending | |
| Step 3 | [ ] Pending | |

---

## Verification

After all steps complete:

- [ ] All tests pass (`pytest -v` / `npm test`)
- [ ] Lints pass (`ruff check .` / `npm run lint`)
- [ ] Manual verification: [Describe how to manually test]
- [ ] Documentation updated
- [ ] PR created with summary

---

## Notes

[Any additional context, links to discussions, or follow-up items]
