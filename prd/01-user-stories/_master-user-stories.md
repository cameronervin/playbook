# Master User Stories

> Consolidated view of all user stories across epics. Number stories
> contiguously (`US-01`, `US-02`, …). Each story has a role, a want, a reason,
> and acceptance criteria. Detailed stories live in the per-epic files; this
> file is the rollup.

## Story Format

```
### US-NN
As a <role>
I want <capability>
So that <benefit>.

#### Acceptance Criteria
1. ...
2. ...
```

## Rollup Table

| ID | Epic | Title | Priority | Status |
|----|------|-------|----------|--------|
| US-01 | Example | Create an example | High | ☐ |
| US-02 | Example | List and view examples | High | ☐ |
| US-03 | Example | Generate example content with the agent | Medium | ☐ |

## Epics

| Epic | File | Summary |
|------|------|---------|
| 1 — Example | [epic-1-example.md](epic-1-example.md) | Core CRUD plus an agent-assisted generation flow for the `Example` entity |

## Stories

### US-01
As a user
I want to create an example
So that I can capture and persist my work.

#### Acceptance Criteria
1. A signed-in user can create an example with a name and optional description.
2. The created example is owned by the user and persisted.
3. Validation errors return a clear message and a 400 response.

### US-02
As a user
I want to list and view my examples
So that I can find and revisit what I created.

#### Acceptance Criteria
1. The list shows only examples owned by the current user.
2. Selecting an example shows its full detail.
3. Requesting an example the user does not own returns 404.

### US-03
As a user
I want the agent to generate example content from a short prompt
So that I can start from a useful draft instead of a blank slate.

#### Acceptance Criteria
1. The user provides a short prompt and receives generated content for the example.
2. The generation runs through the agent framework (chain/graph/executor).
3. Token usage is tracked for the run.
4. Failures return a clear error and never leave a partially-written record.
