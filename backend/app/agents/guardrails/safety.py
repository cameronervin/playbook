"""Deterministic safety checks for athlete chat."""

from __future__ import annotations

from dataclasses import dataclass, field

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
    topic_labels: list[str] = field(default_factory=list)
    risk_labels: list[str] = field(default_factory=list)
    requires_kb_support: bool = False


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
_NIL_TERMS = ("nil", "endorsement", "sponsorship", "brand deal", "compensation")
_COMPLIANCE_TERMS = ("compliance", "ncaa", "eligibility", "violation", "rules")
_RECRUITING_TERMS = ("recruit", "prospect", "official visit", "unofficial visit")
_HARASSMENT_TERMS = ("harassment", "reporting", "misconduct", "abuse", "assault")
_PROCESS_TERMS = ("where do i", "how do i", "upload", "submit", "form", "portal")


def evaluate_athlete_message_safety(message: str) -> AthleteSafetyDecision:
    """Classify an athlete prompt before LLM execution."""
    normalized = message.lower()
    topic_labels = _topic_labels(normalized)
    risk_labels = _risk_labels(normalized)

    if _contains_any(normalized, _EMERGENCY_TERMS):
        return AthleteSafetyDecision(
            bypass_agent=True,
            answer_type="emergency_instruction",
            safety_outcome="emergency",
            response_text=EMERGENCY_RESPONSE,
            topic_labels=topic_labels,
            risk_labels=sorted(set([*risk_labels, "emergency"])),
            requires_kb_support=False,
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
                topic_labels=topic_labels,
                risk_labels=sorted(set([*risk_labels, category])),
                requires_kb_support=False,
            )

    requires_kb = bool(
        set(topic_labels).intersection({"nil", "compliance", "process"})
        or set(risk_labels).intersection({"recruiting", "harassment_reporting"})
    )
    return AthleteSafetyDecision(
        bypass_agent=False,
        answer_type="grounded_answer",
        topic_labels=topic_labels,
        risk_labels=risk_labels,
        requires_kb_support=requires_kb,
    )


def _topic_labels(message: str) -> list[str]:
    labels: list[str] = []
    if _contains_any(message, _NIL_TERMS):
        labels.append("nil")
    if _contains_any(message, _COMPLIANCE_TERMS):
        labels.append("compliance")
    if _contains_any(message, _PROCESS_TERMS):
        labels.append("process")
    return labels


def _risk_labels(message: str) -> list[str]:
    labels: list[str] = []
    if _contains_any(message, _COMPLIANCE_TERMS):
        labels.append("compliance")
    if _contains_any(message, _RECRUITING_TERMS):
        labels.append("recruiting")
    if _contains_any(message, _HARASSMENT_TERMS):
        labels.append("harassment_reporting")
    return labels


def _contains_any(message: str, terms: tuple[str, ...]) -> bool:
    return any(term in message for term in terms)
