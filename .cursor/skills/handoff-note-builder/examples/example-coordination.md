# Example: Coordination / refactor day

**Scenario:** The author spent the day on a refactor that touches several areas and needs careful coordination before merging. Heavier on cross-team handoffs and validation asks.

**Use as anchor for:** Days where the main work is a refactor or change that the team must validate and coordinate around before it lands.

> Names below are placeholders — replace with your real team.

---

Hey All,

Sharing some updates from the day and what to finish by EOD Tomorrow -

Updates:
Codebase
Session persistence refactor - PR raised for review, not merged
I refactored how we persist session state so it survives reconnects. This touches both the API layer and the client store, so I'd like the backend and frontend teams to validate their respective sides before we merge. I'm pretty sure the dynamic fields are getting passed correctly, but please confirm.
Furthermore, there's a chance this impacts the values passed downstream, so test the end-to-end flow rather than just the unit cases.
Testing
I ran a quick load test against the refactor branch - p95 around 130ms, 0% failures over ~2,700 requests. Looks stable, but that was a small profile. We should run the full suite once the PR is reviewed.

What to finish by EOD Tomorrow:
All
Review the session persistence PR I opened, make any adjustments needed, and then merge once both sides have validated.
Frontend
Validate the client store changes in the refactor branch. Confirm reconnect behavior works as expected and the UI state is preserved.
Backend
Validate the API layer changes. Run the full load test profile against the branch and confirm no regressions before merging.
DevOps
<DevOps Lead>
Confirm the staging secrets point at the staging resources, not prod, before we test the refactor there.

Thanks!
<Product> Updates 0331-<timestamp>-Meeting Recording.mp4
