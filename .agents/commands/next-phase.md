
Create the next implementation phase document following this process:

## Steps

1. **Read existing phases** — Read all files in `backstage/prd/03-implementation/` to understand completed work and current phase
2. **Cross-reference PRD** — Review `backstage/prd/01-user-stories/_master-user-stories.md` and `backstage/prd/02-technical-docs/` for requirements
3. **Validate codebase** — Use an explore agent to check which goals are already complete in the codebase
4. **Define goals** — Create logical next goals that build on completed work
5. **Create table** — Build deliverables table with: Status | Goal | Relevant User Stories | Owner(s) | Validation
6. **Write goals** — For each goal:
   - Concise description with scope and key deliverables
   - Map to US-/TS- IDs from user stories
   - Assign owners based on team stack alignment
   - Define concrete validation criteria ("X happens → Y result → Z verified")
7. **Separate concerns** — Split interdependent frontend/backend tasks into distinct line items
8. **Mark complete** — Add ✅ for items verified as complete in codebase
9. **Add team notes** — Highlight coordination dependencies and integration requirements

## Team Context

Replace with your team. Map each member to their stack so goals can be assigned.

| Name | Stack |
|------|-------|
| `<Frontend Lead>` | Frontend |
| `<Backend Lead>` | Backend, Agentic |
| `<Engineer>` | Backend, Agentic |
| `<Engineer>` | Full-stack |

## Output Format

Write to `backstage/prd/03-implementation/phase-{N}.md` using the same format as the previous phase file:

```markdown
### Phase N: [Title]

**Goal:** [High-level phase objective]

**Deliverables:**

| Status | Goal | Relevant User Stories | Owner(s) | Validation |
|--------|------|-----------------------|----------|------------|
| ☐ | **[Goal Name]** — [Description] | US-X, TS-Y | [Owner] | [Validation criteria] |

**Team Notes:**
- [Coordination dependencies]
- [Integration requirements]
```

## Validation Criteria Format

Use this pattern: `Action → Result → Verification`

Example: `Upload file → background job processes it → record updated → status reflects success`
