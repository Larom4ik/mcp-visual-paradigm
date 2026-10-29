"""Centralized relation label sanitizer and clutter reducer for clean UML/ER diagrams."""

import re
from typing import Optional, Tuple

# Common conversational fluff verbs used by LLMs on diagram connectors
STOP_WORDS = {
    # English fluff verbs
    "has",
    "have",
    "having",
    "contains",
    "contain",
    "containing",
    "owns",
    "own",
    "uses",
    "use",
    "using",
    "calls",
    "call",
    "calling",
    "manages",
    "manage",
    "connects",
    "connect",
    "connected_to",
    "associated_with",
    "belongs_to",
    "relates_to",
    "related_to",
    "links_to",
    "points_to",
    "triggers",
    "executes",
    "performs",
    "interacts_with",
    "communicates_with",
    "sends",
    "receives",
    "includes",
    "extends",
    "association",
    "composition",
    "aggregation",
    "generalization",
    "dependency",
    "rel",
    "relation",
    "fk",
    # Russian fluff verbs
    "содержит",
    "состоит_из",
    "имеет",
    "включает",
    "использует",
    "вызывает",
    "относится",
    "связан",
    "связана",
    "связано",
    "пользуется",
    "выполняет",
    "принадлежит",
    "управляет",
    "обращается",
    "отправляет",
    "получает",
    "передает",
    "ассоциация",
    "композиция",
    "агрегация",
    "зависимость",
}


def is_stop_word_label(label: str) -> bool:
    """Return True if label is a generic stop word, fluff phrase, or empty."""
    clean = label.strip().lower().replace("-", "_").replace(" ", "_")
    if not clean:
        return True
    if clean in STOP_WORDS:
        return True
    # Check if phrase is composed entirely of stop words (e.g. 'belongs_to_user' -> role is user)
    parts = [p for p in clean.split("_") if p]
    if all(p in STOP_WORDS for p in parts):
        return True
    return False


def sanitize_class_relation(
    rel_type: str,
    name: str = "",
    source_mult: str = "",
    target_mult: str = "",
) -> Tuple[str, str, str]:
    """Sanitize and normalize a UML Class Diagram relationship.

    Returns:
        Tuple of (clean_name, clean_source_mult, clean_target_mult)
    """
    clean_type = rel_type.strip()
    clean_name = name.strip()
    s_mult = source_mult.strip()
    t_mult = target_mult.strip()

    # Composition and Aggregation: lines must NEVER have textual names
    if clean_type in ("Composition", "Aggregation"):
        clean_name = ""
        # Multiplicities must be present
        if clean_type == "Composition":
            s_mult = s_mult or "1"
            t_mult = t_mult or "1..*"
        elif clean_type == "Aggregation":
            s_mult = s_mult or "1"
            t_mult = t_mult or "0..*"

    # Generalization and Realization: strictly unnamed
    elif clean_type in ("Generalization", "Realization"):
        clean_name = ""
        s_mult = ""
        t_mult = ""

    # Dependency: unnamed by default unless a stereotype is provided
    elif clean_type == "Dependency":
        if is_stop_word_label(clean_name):
            clean_name = ""

    # Association: strip fluff verbs, keep only authentic role names
    elif clean_type == "Association":
        if is_stop_word_label(clean_name):
            clean_name = ""

    return clean_name, s_mult, t_mult


def sanitize_use_case_relation(rel_type: str, name: str = "") -> str:
    """Sanitize a Use Case Diagram relationship.

    Actor-to-UseCase associations are ALWAYS clean unnamed lines.
    Include and Extend are normalized to standard UML stereotypes.
    """
    clean_type = rel_type.strip().capitalize()
    if clean_type == "Association":
        return ""
    if clean_type in ("Include", "«include»", "include"):
        return "«Include»"
    if clean_type in ("Extend", "«extend»", "extend"):
        return "«Extend»"
    return ""


def sanitize_activity_flow(
    source_type: str,
    flow_type: str = "ControlFlow",
    name: str = "",
    guard: str = "",
) -> Tuple[str, str]:
    """Sanitize an Activity Diagram flow label and guard condition.

    Regular flows between actions are always unnamed.
    Outgoing flows from DecisionNode MUST have a guard condition formatted as [condition].

    Returns:
        Tuple of (clean_name, clean_guard)
    """
    clean_guard = guard.strip()
    clean_name = name.strip()

    # If outgoing from Decision, guard is mandatory
    if source_type.strip().lower() == "decision" or clean_guard:
        raw_cond = clean_guard or clean_name
        if raw_cond:
            # Strip outer brackets if present, then re-wrap cleanly
            inner = raw_cond.lstrip("[").rstrip("]").strip()
            if inner:
                formatted_guard = f"[{inner}]"
                return formatted_guard, formatted_guard
        return "[else]", "[else]"

    # Non-decision flows: suppress names to prevent diagram clutter
    return "", ""


def sanitize_deployment_relation(
    rel_type: str,
    name: str = "",
    protocol: str = "",
) -> Tuple[str, str]:
    """Sanitize a Deployment Diagram connection label and protocol.

    Deployment links are strictly «deploy».
    Communication paths strictly display protocol and port, filtering out descriptive verbs.

    Returns:
        Tuple of (clean_name, clean_protocol)
    """
    clean_type = rel_type.strip()
    if clean_type == "Deployment":
        return "«deploy»", ""

    raw_label = protocol.strip() or name.strip()
    if not raw_label or is_stop_word_label(raw_label):
        return "TCP/IP", "TCP/IP"

    # Normalize common port patterns
    lower = raw_label.lower()
    if "443" in lower or "https" in lower:
        return "HTTPS (Port 443)", "HTTPS (Port 443)"
    if "80" in lower and "8080" not in lower and "http" in lower:
        return "HTTP (Port 80)", "HTTP (Port 80)"
    if "5432" in lower or "postgres" in lower:
        return "TCP/IP (Port 5432)", "TCP/IP (Port 5432)"
    if "3306" in lower or "mysql" in lower:
        return "TCP/IP (Port 3306)", "TCP/IP (Port 3306)"
    if "6379" in lower or "redis" in lower:
        return "RESP (Port 6379)", "RESP (Port 6379)"
    if "50051" in lower or "grpc" in lower:
        return "gRPC (Port 50051)", "gRPC (Port 50051)"
    if "5672" in lower or "amqp" in lower or "rabbit" in lower:
        return "AMQP (Port 5672)", "AMQP (Port 5672)"
    if "9092" in lower or "kafka" in lower:
        return "Kafka (Port 9092)", "Kafka (Port 9092)"

    # Clean up excess whitespace and return
    clean_proto = re.sub(r"\s+", " ", raw_label).strip()
    return clean_proto, clean_proto
