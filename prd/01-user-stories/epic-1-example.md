# Epic 1 — Example

> Illustrative epic for the `Example` entity. It covers core CRUD plus an
> agent-assisted generation flow, and demonstrates how to structure stories,
> acceptance criteria, and notes. Replace with your real epics.

## Goal

Let a signed-in user create, view, and manage `Example` records, and draft
example content with the agent.

## Stories

### US-01
As a user
I want to create an example
So that I can capture and persist my work.

> Core CRUD. Establishes the route → service → repository → model path for the
> `Example` entity.

#### Acceptance Criteria
1. A signed-in user can create an example with a name (required) and an optional
   description.
2. The example is persisted and owned by the creating user.
3. Missing/invalid fields return a 400 with a clear validation message.
4. The create flow is covered by a service-level test.

### US-02
As a user
I want to list and view my examples
So that I can find and revisit what I created.

> Read paths, including ownership scoping.

#### Acceptance Criteria
1. The list endpoint returns only the current user's examples.
2. A detail view returns the full example by id.
3. Requesting an example owned by another user returns 404 (not 403, to avoid
   leaking existence).
4. List supports pagination.

### US-03
As a user
I want the agent to generate example content from a short prompt
So that I can start from a useful draft instead of a blank slate.

> Demonstrates the agent framework: a chain assembled into a graph and run by an
> executor, with usage tracking.

#### Acceptance Criteria
1. The user submits a short prompt for an example.
2. The request runs through the agent framework (see
   `prd/02-technical-docs/agentic-framework.md`).
3. Generated content is returned and can be saved onto the example's `data`.
4. Token usage for the run is recorded.
5. On failure, the user gets a clear error and no partial record is written.

## Out of Scope

- Sharing examples between users.
- Versioning / history of generated content.

## Open Questions

- _List anything that needs a product/UX decision before build._
