"""Prompt templates for the LLM-as-judge."""

DEFAULT_PROMPT = """You are a strict evaluator of an AI agent.

You will be given the agent's input, its output, its execution trajectory,
and the expected (reference) output. Score the agent on EACH criterion below.

Criteria:
{criteria}

<input>{input}</input>
<trajectory>{trajectory}</trajectory>
<output>{output}</output>
<expected>{expected}</expected>

Return ONLY valid JSON. For EACH criterion, FIRST write your reasoning in a
"<criterion>_reasoning" string, THEN give the score as a BARE NUMBER (not an
object) within the criterion's stated range. Reason before you score: the score
must follow from the reasoning, not the other way around. No markdown, no preamble.

Example shape for criteria named "accuracy" and "clarity":
{{"accuracy_reasoning": "...", "accuracy": 4, "clarity_reasoning": "...", "clarity": 5}}
"""
