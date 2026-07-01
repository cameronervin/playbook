"""Tool-specific prompt snippets, keyed by (chain, tool_name).

Pattern: when a tool is active for a given chain, its snippet is appended to
that chain's base system prompt by the prompt composer. This keeps tool usage
guidance co-located with the tool and out of the base prompts.
"""

from typing import NamedTuple


class ToolPromptKey(NamedTuple):
    """Identifies a prompt snippet by the chain it targets and the tool it documents."""

    chain: str
    tool_name: str


ATHLETE_KB_PROMPT = """
<tools>
- **search_playbook_knowledgebase**:
Use this tool before making NIL, compliance, recruiting, harassment/reporting,
or department process claims. Query official Playbook athletic department
knowledge base sources with focused, specific search terms.

For supported answers, include every supporting source key returned by this tool
in the structured cited_source_keys field. All shared KB results are
admin-official. If comparable sources conflict, prefer the newest applicable
source_date. Do not invent source keys. If tool results are missing or do not
support the answer, use answer_type "unsupported" and direct the athlete to the
athletic department.
</tools>
"""

ATHLETE_CONVERSATION_FILE_PROMPT = """
<tools>
- **search_conversation_files**:
Use this tool when the athlete asks about uploaded, attached, or
conversation-specific files such as contracts, forms, PDFs, spreadsheets, or
documents. The tool automatically searches only ready files scoped to this
conversation; attached files narrow the private search when present.

Use returned excerpt text as evidence for this conversation only. Source
summaries are orientation only and must not be cited as supporting evidence. For
supported answers, include every supporting source key returned by this tool in
the structured cited_source_keys field. Do not invent source keys, file IDs, or
file contents.
</tools>
"""

DASHBOARD_INSIGHTS_METRIC_PROMPT = """
<tools>
- **inspect_dashboard_metric**:
Use this tool to verify exact dashboard analytics counts before writing summary
claims, headline values, topic counts, unanswered counts, or risk counts. Do not
invent metrics that are not present in the snapshot.
</tools>
"""

DASHBOARD_INSIGHTS_QUERY_EXAMPLES_PROMPT = """
<tools>
- **list_anonymized_query_examples**:
Use this tool to inspect bounded anonymized query examples for a topic, risk, or
unanswered gap. Refer only to message IDs and anonymous user keys. Never infer or
state athlete names, emails, owner IDs, teams, or other identity.
</tools>
"""

ADMIN_CHAT_METRIC_PROMPT = """
<tools>
- **inspect_admin_metric**:
Use this data tool only for exact counts or summary metrics: query volume,
unanswered count, top topics, risk counts, or a full analytics summary. Do not
use it for representative examples, confusion themes, recommendations, stored
insight summaries, or questions already answered by the runtime snapshot.

Accepted metric_name inputs are exactly: analytics.summary, summary,
query_volume, unanswered_count, top_topics, and risk_counts.
metric:analytics.summary is a citation/reference, not a metric_name input. Cite
metric:analytics.summary when using summary metrics. After this tool returns a
relevant metric, stop using data tools and submit the final structured response
unless the user asked for examples or stored insight records too. Do not call
this data tool again with equivalent arguments.
</tools>
"""

ADMIN_CHAT_QUERY_EXAMPLES_PROMPT = """
<tools>
- **list_anonymized_queries**:
Use this data tool for representative anonymized questions, confusion themes,
unanswered gaps, or examples behind a topic/risk. Do not use it for exact
summary counts, generated dashboard insight recommendations, or questions
already answerable from the runtime snapshot and completed insight context.

Filter by topic_label, risk_label, or unanswered_only only when the user asks
for that slice or the snapshot makes the relevant slice clear. Refer only to
anonymized message IDs. Never infer or state athlete names, emails, owner IDs,
teams, provider subjects, or storage keys. After this tool returns relevant
examples, stop using data tools and submit the final structured response unless
the user also asked for exact counts or stored dashboard insights. Do not call
this data tool again with equivalent arguments.
</tools>
"""

ADMIN_CHAT_DASHBOARD_INSIGHTS_PROMPT = """
<tools>
- **list_dashboard_insights**:
Use this data tool for stored generated insights, recommendations, attention
areas, or completed dashboard insight outputs overlapping the current window.
Do not use it for raw query examples, exact summary counts, or general
analytics questions already answered by the runtime context.

Cite dashboard_insight IDs returned by the tool when drawing on stored insight
summaries. After this tool returns relevant stored insights, stop using data
tools and submit the final structured response unless the user also asked for
exact counts or query examples. Do not call this data tool again with equivalent
arguments.
</tools>
"""


TOOL_PROMPT_REGISTRY: dict[ToolPromptKey, str] = {
    ToolPromptKey("athlete_chat", "search_playbook_knowledgebase"): ATHLETE_KB_PROMPT,
    ToolPromptKey("athlete_chat", "search_conversation_files"): (
        ATHLETE_CONVERSATION_FILE_PROMPT
    ),
    ToolPromptKey("dashboard_insights", "inspect_dashboard_metric"): (
        DASHBOARD_INSIGHTS_METRIC_PROMPT
    ),
    ToolPromptKey("dashboard_insights", "list_anonymized_query_examples"): (
        DASHBOARD_INSIGHTS_QUERY_EXAMPLES_PROMPT
    ),
    ToolPromptKey("admin_chat", "inspect_admin_metric"): ADMIN_CHAT_METRIC_PROMPT,
    ToolPromptKey("admin_chat", "list_anonymized_queries"): (
        ADMIN_CHAT_QUERY_EXAMPLES_PROMPT
    ),
    ToolPromptKey("admin_chat", "list_dashboard_insights"): (
        ADMIN_CHAT_DASHBOARD_INSIGHTS_PROMPT
    ),
}
