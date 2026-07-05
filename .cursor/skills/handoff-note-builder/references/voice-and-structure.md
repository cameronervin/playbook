# Voice and Structure Reference

This file captures the voice and structural patterns for the handoff note. Following it keeps drafts indistinguishable from ones the author wrote themselves. Tune the specifics to your author's real voice over time.

## Voice at a glance

The voice is **direct, first-person, pragmatic, and collaborative**. It reads like a thoughtful peer talking to teammates, not a manager dictating tasks. The author writes with authority (they know the product cold) but also with humility (they flag their own uncertainty, ask for validation, share context rather than hoarding it).

**Five adjectives:** direct, informative, warm, unhedged, specific.

## Opening and intro

**Greeting (always):**
```
Hey All,
```

**Intro line (always, right after greeting, with a blank line between):**
```
Sharing some updates from the day and what to finish by EOD <Day> -
```

The `<Day>` is almost always `Tomorrow` for weekday notes. Friday notes use `Monday`. Catch-up notes can name a specific weekday ("EOD Wednesday").

**The trailing hyphen** at the end of the intro line is standard. Keep it.

## Section labels

All section labels are **plain text, no punctuation**, on their own line, followed by content below.

### Updates section

```
Updates:
```
Always followed by a colon. Capitalized U.

Subsections under Updates (in rough frequency order):

| Label | Frequency | When to use |
|---|---|---|
| `Codebase` | Most common | Umbrella for all code changes — default if the day was code-heavy |
| `Timeline` | Occasional | Milestones, deadlines, schedule shifts |
| `Roadmap` | Occasional | Future release planning |
| `Testing` | Occasional | Load testing, UAT, QA results |
| `Migration Plan` / `Timeline/ Migration Plan` | Occasional | Around release/deployment days |
| Feature-specific (e.g. `Voice Mode`, `Auth RBAC`) | As needed | When the day's work splits into distinct streams and "Codebase" is too vague |
| `Focus Group #N` | Rare | Reporting on user research |
| External events | Rare | Non-code work |

Under each subsection, list what happened. Style varies:
- **Short updates:** single line each, flat
- **Detailed updates:** one opening line describing the change, then more lines for the details
- **Status tags inline:** append status to the line: `- merged to dev`, `- pushed to dev`, `- not merged, needs validation before merging`, `- PR raised for <n>`

### What to finish section

```
What to finish by EOD <Day>:
```
Uppercase W. Same day as the intro line. Colon at the end.

Team sections under "What to finish" (in order they typically appear):

| Label | Purpose |
|---|---|
| `All` | Team-wide items everyone needs to know / do |
| `Frontend` | Frontend-specific work |
| `Backend` | Backend-specific work |
| `DevOps` | DevOps-specific work |
| `UI/UX` | UI/UX-specific work |

**Notes on team sections:**
- Order: `All` → `Frontend` → `Backend` → `DevOps` → `UI/UX`. Do not shuffle.
- Skip a section if there are no items. But if including the section, do not leave it empty.
- Within a team section, if specific developers have specific items, put their name on its own line and list their items underneath. Example:
  ```
  Backend
  <Backend Lead>
  Raise the cloud access request for <Backend Dev> if you have not done so already
  Change the staging bucket .env secret to point at the staging bucket rather than prod
  <Backend Dev>
  Continue working with the DevOps team on cache staging provisioning
  ```
- When an item is for the whole team, just list it without a name header.

## Closing

**Sign-off line:**
```
Thanks!
```
Capital T, exclamation mark.

**Meeting recording filename (optional last line):**
If the author records a walkthrough, the format is:
```
<Product> Updates <MMDD>-<YYYYMMDD_HHMMSS>-Meeting Recording.mp4
```
Since you don't know the actual timestamp, include a placeholder:
```
<Product> Updates <MMDD>-<timestamp>-Meeting Recording.mp4
```
and add a brief note after the draft: *"Replace the recording filename with the actual one after recording."* Omit this line entirely if the author doesn't record walkthroughs.

## Sentence-level voice patterns

### How the author talks about their own work

**Attributing changes to themselves:** "I" statements, direct.
- "I tested the application further and did not run into anything else we need to address."
- "I updated the upload memory management to use a spooled tempfile with a semaphore..."
- "I started working on the role-based access cleanup in the backend..."

**Flagging uncertainty or needing review:**
- "Please validate all of this code — the agent was behaving a bit weird when writing it."
- "Overall, I think we need to take another pass at validating the changes I made..."
- "I'm pretty sure this can be done through the SDK parameter..."

**Self-correcting/improving:**
- "I realized we need to build this out a bit more..."
- "Let's simplify this and just add another option..."
- "The initial approach was probably over-complicated, so I updated it..."

### How the author talks to the team

**Direct directives (common for the "What to finish" section):**
- "Take a pull of my most recent changes to dev."
- "Review both PRs I have opened, make any adjustments needed, then merge."
- "Continue testing the application thoroughly and making any changes that come up."
- "Reach out to the DevOps team..."

**Collaborative framing (common in "Updates" when a change is proposed):**
- "We need to..." / "We should..." / "Let's..." / "Our goal should be to..."

**Empowering / trust-building:**
- "Given our team size next week, continue to do a great job communicating and dividing up the Phase N work."
- "This is critical to make sure release 2 doesn't take down prod, so don't feel bad about asking the DevOps team for support."

**Asking for validation / buy-in:**
- "Please validate the changes I made to the globals.css..."
- "Asking for your review on how the loading animation looks..."

**Heads-ups and FYIs:**
- "Quick FYI for those who got the access email..."
- "Just flagging for your awareness."

### Transitional phrases

- "Additionally, ..." — very common, connects related items
- "Furthermore, ..." — emphasis or escalation
- "Like we discussed in today's standup, ..."
- "As a quick note, ..."
- "For [group]: ..."

### Markers the author uses frequently

- **Branch names:** inline, no backticks: `fix/r2-rbac`, `feat/voice-persistence`
- **Commands/env vars:** inline: `.env variable`, `self.retry()`
- **File paths:** inline, sometimes partial: `open-items.md`, `backstage/prd/03-implementation/`
- **URLs:** pasted directly
- **API endpoints:** with paths: `POST /api/v1/files`
- **Metrics:** specific numbers with units: `p95 120ms`, `9.09 RPS`, `2,724 requests`

## Structural quirks

### Capitalization
- Section labels (Updates, Frontend, Backend, etc.) — always capitalized
- Subsection labels under Updates (Codebase, Timeline, Testing, etc.) — capitalized
- Feature-specific labels — title case, technical names preserved (e.g. "RBAC" stays uppercase)
- Days in intro/EOD headers — capitalized (Tomorrow, Monday, Wednesday)

### Line length
No hard limit. Write until the thought is complete, then break. Don't force line breaks for aesthetics.

### Punctuation
- Periods at the end of sentences, usually
- Hyphens surrounded by spaces are common
- Parentheticals common: "(see link)", "(lower priority)"

## Do's and don'ts

**Do:**
- Open with `Hey All,`
- Use `Sharing some updates from the day and what to finish by EOD <Day> -`
- Label updates with plain text section names (no `##` headers)
- Use `I` for the author's own work, `We should/need to` for team-wide direction
- Include `Thanks!` and (if used) a recording filename at the end
- Include inline status on code changes (merged to dev, PR raised, etc.)
- Reference phase implementation plans by name
- Include concrete references: branch names, file paths, URLs, metrics

**Don't:**
- Start with `Hi team,` or `Good morning,` or any other greeting
- Use Markdown bullet characters (`-`, `*`) at the start of content lines
- Use `##` or `###` headers, bold, or italics
- Say "Let me know if you have questions" — not in the voice
- Include a TL;DR or executive summary — the structure is the summary
- Invent attachments or links the author didn't mention
- Add a "signed, <name>" — the note just ends with `Thanks!` + recording

## A short annotated excerpt

```
Hey All,                                          ← Standard greeting. Always.

Sharing some updates from the day and what        ← Standard intro. Day matches EOD header.
to finish by EOD Tomorrow -

Updates:                                          ← Section label, colon, standalone line.
Codebase                                          ← Subsection, no colon, standalone line.
Upload RAM usage - merged to dev                  ← Feature name + status tag inline.
I updated the upload memory management to use a   ← "I" voice, concrete technical detail.
spooled tempfile with a semaphore like we do for
the rest of the codebase.
Slide parallelism                                 ← Next feature, flat under same subsection.
Additionally, I would recommend bumping our       ← "Additionally" transition. "I would
concurrent generation threshold to 6+.              recommend" voice.
```

When in doubt, re-read the examples in `examples/` and mirror what you see.
