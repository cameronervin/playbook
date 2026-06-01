# Team and Products Reference

**This file is a placeholder — edit it with your real team and products.** The skill reads it before drafting to get people/roles/products right. Replace every `<placeholder>` below.

## Products

Most daily notes are focused on a single product. Rare cross-product days are handled in `references/common-scenarios.md`.

### `<Product A>`

- **State:** `<e.g. Active development; Release 2 in testing>`
- **Codebase:** `<git remote URL>`
- **Branches:** `<e.g. dev, staging, main (prod)>`. Describe the merge flow (e.g. dev → staging → main for releases).
- **Implementation plan location:** `prd/03-implementation/` (`_implementation-plan.md` + `phase-*.md` files)
- **Active phase (as of most recent notes):** `<Phase N — Title>`. Update this line as phases advance.
- **Key integrations:** `<e.g. LLM gateway, S3, cache/broker, task queue, vector store>`
- **Notable context the dev team may need reminded of:**
  - `<running concern 1>`
  - `<running concern 2>`

### `<Product B>` (optional — remove if single-product)

- **State:** `<...>`
- **Codebase:** `<git remote URL>`
- **Key integrations:** `<...>`
- **Notable context:**
  - `<...>`

## Team roster

Replace with your actual team. Map each person to a discipline so items can be assigned.

### Engineering

**Frontend**
- `<Frontend Dev 1>` — `<focus / fullstack?>`

**Backend**
- `<Backend Lead>` — `<focus>`
- `<Backend Dev>` — `<focus>`

**DevOps**
- Primary: `<DevOps Lead>`
- Secondary: `<...>`
- DevOps items are typically directed at one of these people by name, with cross-team follow-ups noted

**UI/UX**
- `<Designer>` — current primary UI/UX designer

### Leadership / stakeholders (author's side)

- `<Lead>` — `<role>`
- `<Stakeholder>` — `<role>`

### External / occasional

- `<Name>` — `<external team / role>`

## Common team conventions

- **Name formats:** Use whatever form your team uses on first mention; first names elsewhere.
- **Group vs individual:** Address the whole discipline with the section header (`Frontend`, `Backend`); when an item is specific to one developer, put their name on its own line and list items under it.
- **Common pairings and collaborations:** `<document recurring pairings here>`

## Repeated context blocks

Some context the author includes verbatim when it's needed. Define reusable blocks here and reference them from notes.

### `<Onboarding block>` (example)

Include a minimal version when a new developer is joining:
```
<Product> codebase: <git remote URL>
Refer to the dev branch for the working PRD and implementation plans.
```

### `<Shared credentials / access block>` (example)

```
<Describe shared access the team occasionally needs — never paste real secrets here.
Reference a secrets manager or vault instead.>
```

## Maintaining this file

When the team or products change, edit this file directly. The skill re-reads it each time, so updates take effect immediately.

Useful edits to make over time:
- Add/remove developers as they join or roll off
- Update the "Active phase" line for each product as phases advance
- Add new integrations or external contacts as they emerge
- Revise the "State" line for each product when a release ships
