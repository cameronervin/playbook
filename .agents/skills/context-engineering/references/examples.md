# Context Engineering Examples

Before/after prompt rewrites demonstrating key improvements.

---

## Example 1: Unstructured → XML-Structured Agent Prompt

### Before (Anti-patterns: no XML tags, implicit assumptions, no examples, no error handling)

```
You are a helpful assistant that processes customer support requests.
You can look up customer info, process refunds, and send messages.
Be helpful and professional. If something goes wrong, try to fix it.
Don't share internal information with customers.
```

### After (Structured with XML, explicit rules, examples, error recovery)

```
<role>
You are a customer support agent for Acme Corp. You resolve
billing issues, process refunds, and escalate complex cases.
</role>

<tools>
{tool_descriptions}
</tools>

<rules>
- Always verify customer identity before account changes
- Refunds over $500 require manager approval — use the escalate tool
- Never share internal system IDs with customers
- If unsure, ask the customer for clarification rather than guessing
</rules>

<output_format>
Respond with exactly ONE of:
1. A tool call (to look up data or take action)
2. A message to the customer (only when you have the info needed)
3. An escalation (for cases outside your authority)
</output_format>

<examples>
<example>
<customer_message>I was charged twice for my subscription</customer_message>
<ideal_response>tool_call: lookup_recent_charges(customer_id="{customer_id}", days=30)</ideal_response>
</example>
<example type="negative">
<customer_message>What database do you store my info in?</customer_message>
<ideal_response>I'm not able to share details about our internal systems, but I can assure you your data is stored securely. How can I help you today?</ideal_response>
</example>
</examples>
```

### What improved
- XML tags separate role, tools, rules, output format, examples
- Rules are explicit (refund threshold, identity verification)
- Output format specifies exactly one of three response types
- Includes both positive and negative examples
- Error handling via escalation path

---

## Example 2: Context Dump → Just-in-Time Loading

### Before (Anti-pattern: loading entire state history into every call)

```python
def build_context(user_request, state):
    return [{
        "role": "user",
        "content": f"""
{SYSTEM_PROMPT}

Full conversation history:
{json.dumps(state['all_messages'], indent=2)}

All tool results:
{json.dumps(state['all_tool_results'], indent=2)}

All errors encountered:
{json.dumps(state['all_errors'], indent=2)}

Current request: {user_request}
"""
    }]
```

### After (Compact state, only relevant context for the next decision)

```python
def build_context(user_request: str, state: dict) -> list[dict]:
    return [{
        "role": "user",
        "content": f"""<instructions>
{SYSTEM_PROMPT}
</instructions>

<current_state>
step: {state['current_step']}
completed: {', '.join(state['completed_actions'])}
last_result: {state.get('last_result', 'none')}
errors: {state.get('last_error', 'none')}
</current_state>

<user_request>
{user_request}
</user_request>"""
    }]
```

### What improved
- Only includes current step and last result (not full history)
- Only includes last error (not all errors — stale errors are context poison)
- XML tags separate instructions, state, and user request
- Token count reduced by 80–90% in typical multi-turn conversations

---

## Example 3: Fat Prompt → Lean Prompt with Schema

### Before (Anti-pattern: 600+ word instructions, schema mixed with prose)

```
You are an AI transformation consultant. Your job is to analyze the user's
current business process and generate a comprehensive AI Cascade analysis.
This analysis should cover multiple dimensions including ambition and key
considerations like target KPIs and constraints, process details about
beneficiaries and bottlenecks, performance metrics and cycle times, data
knowledge requirements including sources and formats, agent design covering
capabilities and tools and learning feedback mechanisms, and governance
including compliance requirements and governance frameworks and security
controls. For each section you should provide detailed bullet points using
markdown formatting with dash prefixes. Make sure to cover all areas
thoroughly and don't miss any sections. The output should be valid JSON
with the structure shown below. Remember that missing any field will cause
a validation error so double check your output...
[continues for 400 more words]
```

### After (Concise instructions + explicit JSON schema)

```
<role>
You are an AI transformation consultant. Generate a complete AI Cascade
analysis as JSON from the user's current state process and summary.
</role>

<rules>
- Populate ALL 11 fields below. Missing any field causes a validation error.
- Use 1–2 markdown bullets per field (prefix with "- ").
</rules>

<output_format>
{
  "ambition": {"keyConsiderations": "string"},
  "process": {"processDetails": "string", "performance": "string"},
  "knowledge": {"dataKnowledge": "string"},
  "agentDesign": {"capabilities": "string", "tools": "string", "learningFeedback": "string"},
  "governance": {"compliance": "string", "governanceFramework": "string", "security": "string"}
}
</output_format>

Output ONLY the JSON. No other text.
```

### What improved
- Core instructions under 100 words (was 600+)
- Schema is explicit and separate from prose
- "Output ONLY the JSON" eliminates ambiguity about response format
- Rules section calls out the critical constraint (all 11 fields required)

---

## Example 4: Monolith Agent → Router + Specialists

### Before (Anti-pattern: one agent with every tool)

```python
agent = Agent(
    tools=[search, email, calendar, crm, billing, deploy,
           analytics, notifications, file_upload, reporting],
    system_prompt=MEGA_PROMPT  # 800+ words covering everything
)
```

### After (Router dispatches to focused specialists)

```python
class AgentRouter:
    def __init__(self):
        self.agents = {
            "billing": BillingAgent(
                tools=[lookup_charges, process_refund, escalate],
                system_prompt=BILLING_PROMPT  # 150 words, focused
            ),
            "scheduling": SchedulingAgent(
                tools=[check_calendar, book_meeting],
                system_prompt=SCHEDULING_PROMPT
            ),
            "research": ResearchAgent(
                tools=[web_search, summarize],
                system_prompt=RESEARCH_PROMPT
            ),
        }

    def route(self, user_request: str) -> str:
        intent = classify_intent(user_request)
        return self.agents[intent].run(user_request)
```

### What improved
- Each agent has a focused prompt (fewer tokens, less decision complexity)
- 3–5 tools per agent instead of 10+
- Router uses cheap/fast model for intent classification
- Context windows stay lean — each specialist only sees relevant state

---

## Example 5: No Error Recovery → Structured Error Feedback

### Before (Anti-pattern: crash on tool failure)

```python
result = execute_tool(tool_name, tool_input)
state["steps"].append({"tool": tool_name, "result": result})
```

### After (Feed errors back so agent can self-heal)

```python
try:
    result = execute_tool(tool_name, tool_input)
except Exception as e:
    result = f"""<tool_error>
tool: {tool_name}
error: {str(e)}
suggestion: Try a different approach or ask the user for clarification.
</tool_error>"""

state["steps"].append({"tool": tool_name, "result": result})

if is_stuck(state):
    return "I'm having trouble completing this. Let me escalate."
```

### What improved
- Errors are caught and formatted as structured XML feedback
- Agent can adapt instead of crashing
- Convergence detection prevents infinite retry loops
- Escalation path when self-healing fails
