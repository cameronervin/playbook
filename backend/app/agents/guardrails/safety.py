"""Deterministic safety checks for athlete chat."""

from __future__ import annotations

from dataclasses import dataclass

EMERGENCY_RESPONSE = (
    "I can't help with emergency advice. If this is an emergency, call 911 or "
    "campus emergency services now. If you or someone else may be in immediate "
    "danger or might self-harm, call or text 988 in the U.S. and contact your "
    "athletic department or campus support staff immediately."
)

SENSITIVE_REFUSAL = (
    "I can't provide {category} advice. Please contact the athletic department "
    "or the appropriate campus support office for official help."
)


@dataclass(frozen=True)
class AthleteSafetyDecision:
    """Result of deterministic athlete message safety classification."""

    bypass_agent: bool
    answer_type: str
    safety_outcome: str | None = None
    response_text: str = ""


_EMERGENCY_TERMS = (
    "911",
    "emergency",
    "urgent danger",
    "hurt myself",
    "harm myself",
    "kill myself",
    "suicide",
    "self-harm",
    "self harm",
    "overdose",
    "might hurt himself",
    "might hurt herself",
    "might hurt themselves",
)
_MEDICAL_TERMS = (
    "concussion",
    "diagnose",
    "injury treatment",
    "medical advice",
    "medication",
    "symptoms",
)
_LEGAL_TERMS = (
    "legal advice",
    "legally binding",
    "sue",
    "lawsuit",
    "contract law",
    "lawyer",
)
_MENTAL_HEALTH_TERMS = (
    "panic attack",
    "depression",
    "anxiety",
    "mental health",
    "therapy",
)
def evaluate_athlete_message_safety(message: str) -> AthleteSafetyDecision:
    """Classify an athlete prompt before LLM execution."""
    normalized = message.lower()

    if _contains_any(normalized, _EMERGENCY_TERMS):
        return AthleteSafetyDecision(
            bypass_agent=True,
            answer_type="emergency_instruction",
            safety_outcome="emergency",
            response_text=EMERGENCY_RESPONSE,
        )

    for category, terms in (
        ("medical", _MEDICAL_TERMS),
        ("legal", _LEGAL_TERMS),
        ("mental_health", _MENTAL_HEALTH_TERMS),
    ):
        if _contains_any(normalized, terms):
            return AthleteSafetyDecision(
                bypass_agent=True,
                answer_type="refusal",
                safety_outcome=category,
                response_text=SENSITIVE_REFUSAL.format(
                    category=category.replace("_", " ")
                ),
            )

    return AthleteSafetyDecision(
        bypass_agent=False,
        answer_type="grounded_answer",
    )


def _contains_any(message: str, terms: tuple[str, ...]) -> bool:
    return any(term in message for term in terms)
