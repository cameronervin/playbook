# Context Engineering Reference

Detailed knowledge base for the context engineering skill. Read this when you need deeper guidance on specific techniques.

---

## 1. The Context Engineering Mental Model

Think of the LLM as a CPU, the context window as RAM, and your role as the operating system. You load exactly the right code and data for each step.

**Key constraint**: LLM reasoning starts degrading around ~3,000 tokens of prompt. Technical context windows are much larger, but attention quality drops — the middle 40–60% of the context is the "dumb zone" where signal-to-noise degrades.

**Practical sweet spot**: 150–300 words for core instructions. Data and examples are separate and loaded on demand.

---

## 2. Prompt Structure with XML Tags

XML tags are the preferred way to parse complex prompts for Claude. They eliminate ambiguity about where instructions end and data begins.

### Canonical Structure

```
<role>
[Persona and expertise, 1–3 sentences]
</role>

<tools>
{tool_descriptions}
</tools>

<rules>
- [Explicit constraint 1]
- [Explicit constraint 2]
- [Security/scope guardrail]
- [Error handling instruction]
</rules>

<output_format>
Respond with exactly ONE of:
1. A tool call (to look up data or take action)
2. A message to the user (only when you have what you need)
3. An escalation (for cases outside your authority)
</output_format>

<examples>
<example>
<input>[Scenario]</input>
<ideal_response>[Expected output]</ideal_response>
</example>
<example type="negative">
<input>[Out-of-scope or adversarial input]</input>
<ideal_response>[Correct refusal or redirect]</ideal_response>
</example>
</examples>
```

### Data Positioning Rule

Place longform data (retrieved documents, state dumps, uploaded files) at the **top** of the context. Place queries and instructions at the **bottom**. This can improve response quality by up to 30% because models attend best to the beginning and end of context.

```
[LONGFORM DATA — documents, retrieved context, state]

...

[INSTRUCTIONS — role, rules, output format, query]
```

---

## 3. Tools as Structured Output

Agent tool calls are just the LLM emitting structured JSON that your code routes to a function. Demystify it:

- Define tools as typed data structures (Pydantic models, JSON Schema)
- The LLM **decides**. Your code **executes**.
- Always validate and route through deterministic code — never let the LLM directly execute anything
- Use a `match`/`switch` statement for deterministic routing

```python
from pydantic import BaseModel
from typing import Literal, Union

class LookupCustomer(BaseModel):
    action: Literal["lookup_customer"]
    email: str

class ProcessRefund(BaseModel):
    action: Literal["process_refund"]
    charge_id: str
    amount_cents: int

AgentAction = Union[LookupCustomer, ProcessRefund]

def execute_action(action: AgentAction) -> str:
    match action.action:
        case "lookup_customer":
            return db.find_customer(action.email)
        case "process_refund":
            if action.amount_cents > 50000:
                return "ERROR: Refunds over $500 require escalation"
            return billing.refund(action.charge_id, action.amount_cents)
```

---

## 4. The Agent Loop Pattern

Every production agent reduces to four components:

1. **BUILD CONTEXT** — curate what the LLM sees (just-in-time)
2. **LLM DECIDES** — get structured output
3. **SWITCH** — route to deterministic code
4. **FEED BACK** — add result to state for next iteration

Include convergence detection: if the agent repeats the same tool call 3 times, break and escalate.

---

## 5. Context Window Management Strategies

### Write (Persist Externally)

For long-running tasks, give the agent a scratchpad tool:

```python
SCRATCHPAD_TOOL = {
    "name": "save_notes",
    "description": "Persist important findings to your scratchpad.",
    "input_schema": {
        "type": "object",
        "properties": {
            "key": {"type": "string"},
            "content": {"type": "string"}
        },
        "required": ["key", "content"]
    }
}
```

On context reset, reload the scratchpad into the new context window.

### Select (Just-in-Time Loading)

Only load context relevant to the current decision:

- Retrieve via RAG for large knowledge bases
- Load only the current step's state, not entire history
- Include only the last error (not all errors)
- Include only relevant tool results (not all past results)

### Compress (Summarize History)

When approaching context limits, summarize and restart:

- Use a cheap/fast model to generate a compact state report
- Include: completed actions, current objective, key findings, unresolved items
- Exclude: raw tool call payloads, redundant information

### Isolate (Separate Contexts)

Decompose into specialist agents (3–8 tools each):

- Each agent gets a focused system prompt (fewer tokens)
- Fewer tools means less decision complexity
- Use a router to classify intent and dispatch to the right specialist

---

## 6. Error Recovery Patterns

### Structured Error Feedback

```xml
<tool_error>
tool: {tool_name}
error: {error_message}
suggestion: Try a different approach or ask the user for clarification.
</tool_error>
```

### Rules

- Feed errors back into context so the agent can self-heal
- Once an error is resolved, **clear it from context** — stale errors become "context poison"
- After 2–3 failed attempts at the same action, escalate to human

---

## 7. Human-in-the-Loop

Make human escalation a first-class tool, not an edge case:

```python
HUMAN_APPROVAL_TOOL = {
    "name": "request_human_approval",
    "description": "Request human approval for high-stakes actions.",
    "input_schema": {
        "type": "object",
        "properties": {
            "action_description": {"type": "string"},
            "risk_level": {"type": "string", "enum": ["medium", "high", "critical"]},
            "reversible": {"type": "boolean"}
        },
        "required": ["action_description", "risk_level", "reversible"]
    }
}
```

Use for: refunds over thresholds, account deletions, production deployments, any irreversible action.

---

## 8. Evals

Build evals before tweaking prompts. You cannot improve what you don't measure.

### Eval Case Structure

```python
{
    "input": "User message or scenario",
    "expected_first_tool": "tool_name",
    "expected_contains": ["keyword1", "keyword2"],
    "should_not_contain": ["sensitive_data", "internal_id"],
}
```

### Key Principles

- Include **negative examples** — they define boundaries and prevent over-triggering
- Test tool selection accuracy (did the agent pick the right tool?)
- Test output content (does it contain/exclude expected keywords?)
- Test edge cases (ambiguous input, missing data, adversarial input)
- Run evals automatically on prompt changes

---

## 9. Owning Your Prompts

Treat prompts as production code:

- **Hand-craft** every token that enters the context window
- **Version-control** prompts alongside application code
- **Never** rely on framework-generated prompts — they hide what's sent to the model
- **Audit** prompts on every change — know exactly what the model sees
- **Iterate** with evals — measure before and after each change

---

## 10. Agent Decomposition Heuristics

| Signal | Action |
|---|---|
| Agent has 10+ tools | Split into specialist agents |
| Prompt exceeds 500 words of instructions | Extract data/examples, compress instructions |
| Agent handles 3+ unrelated task types | Create a router + specialists |
| Context window fills within 5–10 turns | Add compaction strategy |
| Agent loops on the same action | Add convergence detection + escalation |
| Tool calls fail > 20% of the time | Add structured error feedback + retry logic |
