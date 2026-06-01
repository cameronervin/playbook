# Note Skeleton Template

This is the structural scaffolding for a handoff note. Fill in the bracketed sections with content derived from the author's brain dump, the active phase file, and the voice/structure rules.

**Do not output the angle brackets in the final draft. Do not output the inline comment lines (starting with `#`) — they're guidance for you, not part of the note.**

---

```
Hey All,

Sharing some updates from the day and what to finish by EOD <Day> -

Updates:
<subsection label — typically "Codebase"; or "Timeline", "Testing", "Roadmap", or a feature-specific label>
<content lines — what was done, status tags inline where relevant>
<subsection label if needed>
<content lines>
# Repeat subsections as needed. For a light day, one subsection is enough.

What to finish by EOD <Day>:
All
<team-wide items — priority guidance, cross-team coordination, things everyone should know>
# Omit "All" if no team-wide items.
Frontend
<items for the full frontend team, or see individual callouts below>
<Developer name 1 — e.g. "<Frontend Dev>">
<items specific to that developer>
# Omit developer callouts if items apply to the whole frontend team.
Backend
<items for the full backend team, or individual callouts below>
<Developer name>
<items specific to that developer>
DevOps
<DevOps lead name>
<DevOps items — infra, cloud access, CI/CD, external provisioning, provider follow-ups>
UI/UX
<Designer name>
<UI/UX items — wireframe requests, design reviews, new modal content>
# Omit UI/UX if no items for the day.

Thanks!
<Product> Updates <MMDD>-<timestamp>-Meeting Recording.mp4
# Drop the recording line entirely if the author doesn't record walkthroughs.
```

---

## Minimal variant (light day)

```
Hey All,

Sharing some updates from the day and what to finish by EOD Tomorrow -

Updates:
<single subsection>
<brief content>

What to finish by EOD Tomorrow:
All
<team-wide direction>
Frontend
<brief items>
Backend
<brief items>

Thanks!
<Product> Updates <MMDD>-<timestamp>-Meeting Recording.mp4
```

(Skip DevOps and UI/UX if nothing for them that day.)

## Expanded variant (onboarding day)

For an onboarding day, add pre-sections between the intro and `Updates:`:

```
Hey All,

Sharing some updates from the day and what to finish by EOD Tomorrow -

Onboarding:
<welcome + context for the new person>

Product:
<repo link, PRD location, access info, key concepts>

Access, etc.
<accounts / VPN / repo invite / API keys — reference a secrets manager, never paste secrets>

Updates:
<normal updates section for the rest of the team>

What to finish by EOD Tomorrow:
<normal team sections, with specific items for the new dev>

Thanks!
<Product> Updates <MMDD>-<timestamp>-Meeting Recording.mp4
```

## Key formatting rules

1. One blank line between the greeting and the intro line.
2. One blank line between the intro line and `Updates:`.
3. One blank line between the last `Updates:` content and `What to finish by EOD...:`.
4. One blank line before `Thanks!`.
5. Subsection labels (`Codebase`, `Frontend`, etc.) are on their own lines. No colon, no markdown formatting.
6. Content lines follow the subsection label directly — no bullet characters.
7. Individual developer names within a team section are on their own lines, items follow directly.

## What NOT to put in the skeleton

- No TL;DR section
- No "Summary" header
- No "Questions / Blockers" section (weave these into the flow)
- No "Links" section (links appear inline where the context sits)
- No formal closing like "Best regards" — `Thanks!` is it
