---
name: handoff-note-builder
description: Drafts end-of-day handoff notes from a product lead to their development team, matching an established voice and format. Use whenever the user mentions writing a handoff note, EOD note, EOD update, daily ping to the dev team, overnight handoff, writing up "what I did today and what the team needs to do tomorrow," or describes a day's progress in a lead-to-dev context. Also triggers when the user says "help me write my note," "draft my note," "put together my update for the team," or pastes a brain dump of what they worked on and what's next. Use this skill instead of drafting a generic update — the note has a specific structure and voice that must be preserved.
---

# Handoff Note Builder

> **This is a genericized template skill.** Edit `references/team-and-products.md` with your real
> products, team, and conventions before relying on it. Placeholders look like `<Product>`,
> `<Frontend Dev>`, `<Backend Lead>`.

## Purpose

This skill helps a product lead / IC draft a daily end-of-day handoff note for their dev team. When the team works after the author logs off (e.g. a different timezone), the note is what keeps them unblocked overnight. It is typically sent as a chat/Teams message.

The goal is a **fast, low-friction draft** that the author can edit lightly and send. The author is busy; do not interrogate them. Accept brain dumps, infer structure, fill in the template, and ask targeted questions only when critical context is missing.

## When this skill triggers

Any of these cues should trigger the skill:
- "Help me write my handoff note"
- "Draft my EOD note"
- "Write up what I did today for the team"
- "Put together my update for the team"
- A brain dump like: "Today I fixed X, merged Y, team needs to test Z tomorrow"
- Any phrasing where the author is summarizing a workday and wants it formatted for the dev team

## The note structure (non-negotiable)

Every note follows this exact skeleton. Do not improvise new top-level sections. See `templates/note-skeleton.md` for the fillable template and `examples/` for reference outputs.

```
Hey All,

Sharing some updates from the day and what to finish by EOD <Tomorrow|Monday|...> -

Updates:
<subsection 1>
<content>
<subsection 2>
<content>
...

What to finish by EOD <Tomorrow|Monday|...>:
All
<team-wide items>
Frontend
<frontend items, optionally broken out by developer name>
Backend
<backend items, optionally broken out by developer name>
DevOps
<devops items, optionally broken out by developer name>
UI/UX
<UI/UX items>

Thanks!
<Product> Updates <MMDD>-<timestamp>-Meeting Recording.mp4
```

**Critical notes on the structure:**
- The greeting is always `Hey All,`.
- The day in the intro line and the day in the "What to finish by EOD" header must match. If the author is writing Friday and will be back Monday, both read "Monday." For an evening note about the next day's handoff, "Tomorrow" is fine.
- The last line is an optional meeting recording filename (if the author records a voiceover walkthrough). Include a placeholder like `<Product> Updates <MMDD>-<timestamp>-Meeting Recording.mp4` and note that they should paste the actual filename after recording. Drop this line entirely if the author doesn't record walkthroughs.
- The "All" team section is optional and included only when there are genuinely team-wide items.
- Team sections (`Frontend`, `Backend`, `DevOps`, `UI/UX`) are the standard four. Not every note uses every section — omit sections that have no items for the day.
- Within a team section, if items are specific to one developer, write that developer's name on its own line and list their items underneath. See examples.

For detailed voice patterns (phrasing, transitions, sign-offs, quirks), read `references/voice-and-structure.md`. Read this before writing — the voice is specific and matters.

## Workflow

### Step 1: Identify product and day

Before drafting, you need two things:

1. **Product** — which product is this note for? If the team owns more than one and you can't tell from context, ask.
2. **Target day** — "Tomorrow" is the default. Use "Monday" for Friday notes, or name the specific weekday for mid-week catch-up notes. Infer from context when possible.

### Step 2: Load context

Read these in order (skip what isn't available):

1. **`references/team-and-products.md`** — always read this. It tells you who's on which team, which product has what context to mention, and common collaborators.
2. **The active implementation phase file** — run `scripts/gather_phase_context.py` to find the current phase file in `prd/03-implementation/`. If you have no filesystem access, ask the author to paste the current phase content or tell you which phase they're in.
3. **The previous note (if available)** — skim it for carry-over items. Don't invent carry-overs; only reference what's actually there.
4. **`references/voice-and-structure.md`** — read this before drafting so the voice comes out right.

### Step 3: Elicit the author's content

This is the most important step. The content is **mostly in their head** — there is no ticket board to scrape. Your job is to extract it efficiently.

**Default mode: accept a brain dump.** If the author has already described what they did and what's next (even loosely), that's enough to start. Draft from it and let them revise. Do not ask 10 questions if they've given you a paragraph.

**When the input is very sparse** ("help me write my note"), ask at most **two** targeted questions, combined into a single message:

> Quick context to shape the draft:
> 1. What did you ship or move forward today? (bullet points fine)
> 2. What's the top priority for the team tomorrow, and any specific devs you want to address?

Do NOT ask separate questions for every section. Infer sections from the brain dump; if something's missing, the author will add it during revision.

**What to accept as input without asking:**
- Feature names, branch names, PR links, markdown filenames — use them as given
- Partial developer names — look them up in `references/team-and-products.md` to confirm which team
- Vague references — if the previous note or phase file clarifies, use that; otherwise mirror the author's language

### Step 4: Draft the note

Assemble the draft using the skeleton, the voice rules, the brain dump as content source, and the phase file / previous note for surrounding context.

**Key drafting principles:**

1. **First person, author voice.** "I fixed...", "I'm thinking we should...", "I'll update tomorrow."
2. **Use the exact subsection patterns.** Under `Updates:`, common subsections are `Codebase` (default umbrella for all code work), `Timeline`, `Roadmap`, `Testing`, `Migration Plan`, plus occasional feature-specific labels. Use feature-specific labels when the day's work splits into distinct streams.
3. **Status shorthand.** Include status inline: `- merged to dev`, `- pushed to dev`, `- not merged, needs validation before merging`, `- PR raised for <name>`.
4. **Reference the phase plan explicitly.** "See the Phase N implementation plan," "update the markdown file statuses once completed" are standard.
5. **Name developers for team-specific items.** Put their name on its own line under the team section and list their items under it.
6. **Don't pad.** If the author had a light day, the note can be short. Match the day, not a word count.
7. **Only include items the author mentioned or that are clearly in scope** from the phase file / previous note. Do NOT invent tasks.
8. **Sign off with `Thanks!`** followed by the optional recording filename placeholder.

### Step 5: Present and iterate

Show the draft in a copy-pasteable block. After the draft, offer common adjustments (shorten/expand a section, add/remove a developer callout, change tone, shift items between "Updates" and "What to finish"). Iterate based on feedback — most notes need 1-2 passes.

## Handling common scenarios

See `references/common-scenarios.md` for tailored guidance on recurring situations:
- **Cleanup/close-out day** (end of a phase)
- **Migration day / code freeze** (high coordination)
- **Light day** (quiet progress, short note)
- **Onboarding day** (new developer joining — heavy context section)
- **Cross-product day** (two products in one note — rare)
- **Blocked day** (waiting on DevOps, external dep)

## Output format

Produce the draft as **plain text with chat-compatible formatting**. The author pastes this into a chat tool, which interprets line breaks and indentation.

**Do not use Markdown bullet characters (`-`, `*`) at the start of content lines.** Rely on indentation and line structure — that's what the team is used to seeing.

**Do not wrap the draft in triple backticks** unless explicitly asked. Present it inline so the author can copy it cleanly.

## What NOT to do

- **Don't invent action items** the author didn't mention.
- **Don't add formal headers** like `## Updates` or `### Frontend`. Use plain text section labels (just the word on its own line).
- **Don't over-apologize or hedge.** The voice is direct and confident.
- **Don't convert the note into bulleted Markdown.** Preserve the flat-text-with-indentation style.
- **Don't skip the recording placeholder** if the author records walkthroughs — it's the last line.
- **Don't mention the skill or tool** in the draft. It should read like the author wrote it.
- **Don't forget that the day in the intro must match the "What to finish" header.**

## Quick-reference: what to read when

| Situation | File to read |
|---|---|
| Always, before drafting | `references/voice-and-structure.md` |
| Always, before drafting | `references/team-and-products.md` |
| Need a structural template | `templates/note-skeleton.md` |
| Unfamiliar situation (e.g. migration day) | `references/common-scenarios.md` |
| Need a voice anchor | `examples/example-midphase.md` or another example |
| Need to find active phase | `scripts/gather_phase_context.py` |
