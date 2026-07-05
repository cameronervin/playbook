
# Implement Feature (TDD Workflow)

Implement features using Test-Driven Development following the Harness Engineering principles. This skill ensures code quality, proper documentation, and architectural consistency.

## When to Use

- New features (3+ steps or new logic)
- Non-trivial bug fixes
- Refactoring existing functionality
- Any change touching multiple layers

## Workflow

### 1) Preflight Context

Before writing any code, gather context:

```bash
# Check current state
git status -sb
git diff --stat

# Read relevant documentation
# - backstage/architecture/overview.md for system understanding
# - backstage/prd/05-user-stories.md for requirements
# - implementation/remaining-work.md for current priorities
```

**Identify:**
- Which layers are affected (api/v1, services, repositories, models)?
- Which user stories does this relate to (US-XX, TS-XX)?
- Are there existing patterns to follow?
- What tests already exist for related functionality?

### 2) Plan the Approach

For simple features (1-2 files, clear requirements):
- State approach in 2-3 sentences
- Identify the test file and implementation file

For complex features (3+ files, cross-cutting concerns):
- Create an execution plan using [references/feature-template.md](references/feature-template.md)
- Document decisions as you go
- Consider creating an ADR if architectural decisions are involved

**Ask if unclear:**
- Multiple valid approaches exist
- Requirements are ambiguous
- Breaking changes are needed
- New dependencies are required

### 3) RED: Write Failing Test First

Write a test that describes the expected behavior:

```python
# Backend example
def test_feature_does_expected_behavior():
    # Arrange
    service = FeatureService()
    
    # Act
    result = service.do_something(input_data)
    
    # Assert
    assert result.status == "success"
    assert result.value == expected_value
```

```typescript
// Frontend example
describe('FeatureComponent', () => {
  it('should render expected output', () => {
    render(<FeatureComponent data={mockData} />);
    expect(screen.getByText('Expected Text')).toBeInTheDocument();
  });
});
```

**Run the test to confirm it fails:**

```bash
# Backend
cd backend && pytest -v -k "test_feature"

# Frontend
cd frontend && npm test -- --grep "FeatureComponent"
```

### 4) GREEN: Minimal Implementation

Write the **minimum** code to make the test pass:

- Don't add extra features
- Don't optimize prematurely
- Don't refactor yet
- Just make the test green

```bash
# Run test again to confirm it passes
cd backend && pytest -v -k "test_feature"
```

### 5) REFACTOR: Clean Up

With tests passing, improve the code:

- Extract constants for magic strings/numbers
- Improve naming for clarity
- Remove duplication
- Ensure proper error handling
- Add type hints (Python) or TypeScript types

**Keep tests green throughout refactoring.**

### 6) Verify

Run full verification before completing:

```bash
# Backend
cd backend && pytest -v
cd backend && ruff check .

# Frontend
cd frontend && npm test
cd frontend && npm run lint
```

**Update documentation if needed:**
- New endpoint? Update `backstage/api/endpoints.md`
- New tool? Update `backstage/agents/tools.md`
- Architecture change? Create ADR in `backstage/architecture/decisions/`

### 7) Output Summary

After implementation, provide a structured summary:

```markdown
## Implementation Summary

**Feature:** [Name/Description]
**User Stories:** US-XX, TS-XX

### Files Changed
- `path/to/file.py` - [What was changed]
- `path/to/test_file.py` - [Tests added]

### Tests Added
- `test_feature_does_x` - Verifies X behavior
- `test_feature_handles_edge_case` - Verifies edge case

### Documentation Updated
- [List any docs updated]

### Verification
- [ ] All tests pass
- [ ] Lints pass
- [ ] Docs updated
```

## TDD Checklist

See [references/tdd-checklist.md](references/tdd-checklist.md) for detailed step-by-step checklist.

## Execution Plan Template

For complex features, use [references/feature-template.md](references/feature-template.md) to create a detailed plan.

## Anti-Patterns to Avoid

| Anti-Pattern | Do Instead |
|--------------|------------|
| Write implementation first | Write failing test first |
| Write many tests at once | One test at a time |
| Over-engineer initial solution | Minimal code to pass test |
| Skip refactoring step | Always refactor after green |
| Ignore failing tests | Fix or remove broken tests |
| Copy-paste without understanding | Understand patterns, then apply |
