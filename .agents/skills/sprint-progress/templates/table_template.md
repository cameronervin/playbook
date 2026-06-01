# Sprint Progress Report - {{DATE}}

## Summary

| Metric | Count |
|--------|-------|
| Total Stories | {{TOTAL}} |
| Completed | {{COMPLETED}} |
| In Progress | {{IN_PROGRESS}} |
| Not Started | {{NOT_STARTED}} |

---

{{#PHASES}}
## Phase {{PHASE_NUM}}: {{PHASE_NAME}}

| Status | Story ID | Description |
|--------|----------|-------------|
{{#STORIES}}
| {{STATUS}} | {{STORY_ID}} | {{DESCRIPTION}} |
{{/STORIES}}

{{/PHASES}}

---

## Status Legend

| Status | Meaning | Color |
|--------|---------|-------|
| Completed | Work finished and validated | Green |
| In Progress | Currently being worked on | Blue |
| Not Started | Not yet begun | White |

---

*Generated on {{DATE}} by Sprint Progress Tracker*
