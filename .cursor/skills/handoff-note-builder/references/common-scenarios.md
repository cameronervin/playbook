# Common Scenarios

Handoff notes take on different shapes depending on where the team is in the release cycle and what happened that day. This file gives a starting recipe for each recurring scenario — which sections to include, what the voice leans toward, and what content typically shows up.

Treat these as soft templates. The actual note should adapt to the author's brain dump — don't force a scenario if it doesn't fit.

## Scenario: In-flight development day

**When:** Mid-phase development. Team is heads-down shipping features. The most common shape.

**Typical content:**
- `Updates: > Codebase` with 2-5 items worked on or reviewed. Inline statuses (`merged to dev`, `pushed to dev`, `PR raised for <n>`).
- Sometimes a second subsection for a larger initiative.
- `What to finish by EOD Tomorrow:` with items for each active team.
- Individual developer callouts when specific tasks need specific owners.

**Voice tilt:** Collaborative, forward-looking. "We should..." "Continue...". Light on ceremony.

**Length:** 600-1200 words typically.

## Scenario: Cleanup / close-out day (end of a phase)

**When:** A phase is wrapping up; remaining items are being chased and the next phase is being shaped.

**Typical content:**
- `Updates:` focused on what was closed out that day, status of the phase markdown file, and what remains.
- Often a `Phase N: Cleanup Close Out` or `Phase N: Testing` subsection under each team.
- "Update the markdown file statuses once completed" is a common recurring instruction.
- Sometimes a heads-up about what's coming in the next phase.

**Voice tilt:** Focused, tidy-up energy. "Address the remaining items assigned to you in section 2 of the phase N plan."

**Length:** 500-900 words.

## Scenario: Migration / release day

**When:** Code freeze, staging → prod migration, or a high-coordination release day.

**Typical content:**
- `Updates: > Timeline/ Migration Plan` subsection. Explains the plan and any timing shifts.
- Detailed DevOps coordination.
- Lists of what must be ready before the migration window: DB updates, env var changes, secrets, seed data, permissions.
- `What to finish by EOD Tomorrow:` with a single headline priority repeated at the top of each team section.

**Voice tilt:** Careful and coordinative. More "we" than "I". Emphasis on making sure nothing gets dropped.

**Length:** 800-1500 words. Can be the longest notes of the cycle.

## Scenario: Light / quiet day

**When:** The author had meetings, a light code day, or spent time on strategy/roadmap.

**Typical content:**
- Shorter `Updates:` — often just one subsection (Roadmap, etc.).
- "What to finish" may be continuation items ("continue to...", "follow up on...").
- FYI-heavy voice.

**Voice tilt:** Informational. "No action needed here, just an FYI."

**Length:** 400-700 words.

## Scenario: Onboarding day (new developer)

**When:** A new developer is joining the team or ramping onto a new product.

**Typical content:**
- Heavy Onboarding / Product / Access context at the top before Updates.
- References the repo URL, the PRD/implementation plan locations, key access (accounts, API keys, repo invites).
- Clear "spend some time familiarizing yourself" direction for the new dev.
- Continued regular updates for the rest of the team below.

**Voice tilt:** Welcoming, generous with context. Assumes the new person hasn't seen anything.

**Length:** Often the longest notes (1500-2200 words).

**Useful blocks to include** (from `references/team-and-products.md`):
- Repo URL for the product
- Onboarding / access block (reference a secrets manager — never paste real secrets)
- Short description of `backstage/prd/` structure

## Scenario: Blocked day (waiting on DevOps or external dep)

**When:** The team is blocked on something external (DevOps provisioning, a data service, a third-party API).

**Typical content:**
- `Updates:` acknowledges the block honestly.
- Explicit guidance on what to do while blocked: "If we're blocked by the staging environment, address remaining items from Phase N and test locally."
- DevOps section has explicit follow-up items, often with encouragement to ask for support.

**Voice tilt:** Practical, unpanicked. Gives the team permission to pivot to Plan B.

**Length:** 500-800 words.

## Scenario: Testing/UAT-focused day

**When:** The team is running load tests, UAT, or bug bashing.

**Typical content:**
- `Updates: > Testing` subsection with specific metrics and findings (p95/p99 latencies, RPS, failures).
- Specific bug callouts with repro info.
- `What to finish by EOD Tomorrow:` directs the team to continue testing, address specific bugs, prep for the next readiness gate.

**Voice tilt:** Data-driven, specific. Lots of concrete numbers and endpoint names.

**Length:** 700-1200 words.

## Scenario: Cross-product day (two products in one note)

**When:** Rare. Usually a transition between products, or a small hotfix on a secondary product while the main one is the focus.

**Typical content:**
- The main product gets the standard full structure.
- The secondary product is included as a separate block of updates + items, under a clearly labeled section like `<Product B>:` in the middle of the note.
- The recording filename uses an "X x Y" format: `<Product A> x <Product B> Updates ...`

**Voice tilt:** Same as usual but with explicit context shifts. "For `<Product B>`:" or "Switching to `<Product B>` for a moment:"

**Length:** 1000-1500 words.

## Scenario: Post-milestone / reflective day

**When:** The day after a big ship, launch, or external event.

**Typical content:**
- `Updates:` may include a "this is a testament to the team" type acknowledgment.
- Roadmap or retrospective content.
- Lighter "What to finish" section.

**Voice tilt:** Warm, appreciative. "Great work so far team."

**Length:** 500-800 words.

---

## How to use this file

When starting a draft, quickly match the day to a scenario based on the author's brain dump. Then:
1. Use the scenario's typical content list as a checklist — are there items the author hinted at that fit this shape?
2. Let the scenario's voice tilt flavor the phrasing without overriding the author's own words.
3. Aim for the scenario's typical length, but follow the day. A blocked day is shorter; a migration day is longer.

If the day doesn't fit any scenario cleanly, follow the default "in-flight development day" recipe.
