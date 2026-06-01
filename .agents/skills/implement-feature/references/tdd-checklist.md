# TDD Checklist

Step-by-step checklist for Test-Driven Development workflow.

## Before Starting

- [ ] Read relevant documentation (`docs/`, `prd/`, `implementation/`)
- [ ] Identify affected layers and files
- [ ] Check for existing tests and patterns
- [ ] Understand the user story requirements

## RED Phase: Write Failing Test

- [ ] Create or open test file in appropriate location
  - Backend: `backend/tests/` mirroring `backend/app/` structure
  - Frontend: Co-located `*.test.tsx` or `__tests__/` folder
- [ ] Write test with clear name describing expected behavior
- [ ] Use Arrange-Act-Assert pattern
- [ ] Include edge cases if obvious
- [ ] Run test and **confirm it fails**
- [ ] Failure should be for the right reason (missing implementation, not syntax error)

## GREEN Phase: Minimal Implementation

- [ ] Write the minimum code to pass the test
- [ ] Don't add extra features or optimizations
- [ ] Don't worry about code style yet
- [ ] Run test and **confirm it passes**
- [ ] If test still fails, debug and fix

## REFACTOR Phase: Clean Up

- [ ] Extract magic strings/numbers to constants
- [ ] Improve variable and function names
- [ ] Remove code duplication
- [ ] Add proper error handling
- [ ] Add type hints (Python) or TypeScript types
- [ ] Run tests after each change - **keep them green**
- [ ] Check for SOLID violations:
  - [ ] Single Responsibility: Does this do one thing?
  - [ ] Open/Closed: Can it be extended without modification?
  - [ ] Dependency Inversion: Are dependencies injected?

## Verification

- [ ] Run full test suite (not just new tests)
- [ ] Run linter and fix any issues
- [ ] Check for type errors
- [ ] Review changes with `git diff`

## Documentation

- [ ] Update API docs if endpoint changed (`docs/api/endpoints.md`)
- [ ] Update tool docs if tool changed (`docs/agents/tools.md`)
- [ ] Create ADR if architectural decision made
- [ ] Update remaining-work.md if completing a tracked item

## Final Checklist

- [ ] All tests pass
- [ ] No linter errors
- [ ] No type errors
- [ ] Documentation updated
- [ ] Code follows existing patterns
- [ ] Changes are minimal and focused
