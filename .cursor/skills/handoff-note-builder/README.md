# Handoff Note Builder — Installation & Usage

A skill for drafting daily EOD handoff notes from a product lead to their dev team.

> **Genericized template.** Before relying on it, edit `references/team-and-products.md` with your
> real products, team, and conventions. All examples use placeholders like `<Product>` and `<Backend Lead>`.

## What this solves

Writing handoff notes is time-consuming because the content lives in your head, not in a ticket board. This skill:

- Accepts a brain dump and structures it into a consistent note format
- Reads `backstage/prd/03-implementation/` to identify the current active phase and pull relevant context
- Keeps a specific voice, section structure, and tone the team expects
- Only asks clarifying questions when context is genuinely missing (max two)
- Iterates quickly — most notes land in 1–2 revision passes

## Install

### Claude Code

Skills live in `~/.claude/skills/` (user-level, works everywhere) or `<repo>/.claude/skills/` (project-level).

```bash
mkdir -p ~/.claude/skills
cp -r handoff-note-builder ~/.claude/skills/
```

Result: `~/.claude/skills/handoff-note-builder/SKILL.md` and its companions. (This scaffold ships it under `.cursor/skills/` for Cursor; copy it wherever your tool loads skills from.)

## First-time setup (5 minutes)

After installing, open `references/team-and-products.md` and replace the placeholders:

1. **Products** — name your product(s) and set the "Active phase" line. Update it as phases advance.
2. **Team roster** — add your developers under Frontend / Backend / DevOps / UI/UX.
3. **Repeated context blocks** — define onboarding/access blocks. Reference a secrets manager — never paste real secrets.

The skill reads this file every time it runs, so edits take effect immediately.

## How to use

Once installed, just describe your day. Examples of what works:

**Minimal brain dump:**
> "Write my handoff note. Today I fixed the RBAC bug in fix/rbac, not merged. Tomorrow the team needs to validate and merge, plus `<DevOps Lead>` should follow up on cloud access."

**Detailed brain dump:**
> "Handoff note for tomorrow. Today: load tested the release with 4 profiles, 0% failures, p95 sub-150ms. Pushed the migration timeline to Friday. Tomorrow: team preps the migration package and coordinates with DevOps."

**Nearly zero context:**
> "Help me write my note for today."
> *(Skill will ask two targeted questions.)*

## What the skill produces

A plain-text draft you can paste into your chat tool:

- `Hey All,` greeting
- `Updates:` section with appropriate subsections (`Codebase`, `Timeline`, feature-specific labels)
- `What to finish by EOD Tomorrow:` with team breakdowns (All, Frontend, Backend, DevOps, UI/UX)
- Individual developer callouts where appropriate
- `Thanks!` sign-off + optional meeting recording filename placeholder

## Tuning the skill to your voice

After using it for a week, if the drafts consistently miss your voice, edit:

- `references/voice-and-structure.md` — voice patterns, phrasing, quirks
- `references/common-scenarios.md` — recipes for recurring situations
- `examples/` — add a real note you're happy with as a new anchor example

## Structure of the skill

```
handoff-note-builder/
├── SKILL.md                      # Main workflow — Claude reads this first
├── references/
│   ├── voice-and-structure.md    # Style guide for the note voice
│   ├── team-and-products.md      # Team roster + product context (EDIT THIS)
│   └── common-scenarios.md       # Recipes for recurring note shapes
├── examples/
│   ├── example-midphase.md       # Mid-phase development day
│   ├── example-cleanup.md        # Phase close-out day
│   └── example-coordination.md   # Refactor + coordination day
├── templates/
│   └── note-skeleton.md          # Fillable structural template
└── scripts/
    └── gather_phase_context.py   # Reads backstage/prd/03-implementation/ to find active phase
```

## Things to watch for

- **The recording filename placeholder** — the skill can't know the actual timestamp, so it leaves a placeholder you fill in after recording. Drop the line if you don't record walkthroughs.
- **The skill won't invent action items** — only items you mentioned appear in the draft. This is deliberate.
- **The skill assumes "Tomorrow" by default** — say "Monday" if it's Friday, or name the weekday for catch-up notes.

## Iterating on the skill

If drafts miss the mark, paste the actual note you ended up sending and ask: "compare my final version to your draft and update the skill to prevent the same gaps next time."
