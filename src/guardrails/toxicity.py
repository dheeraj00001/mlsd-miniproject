"""Toxicity Detection Guardrail (L4).

Scans free-text inputs and generated model outputs for abusive, toxic,
harmful, or profane content to maintain safe operational communication.
"""

import logging
import re
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Heuristic patterns for toxic, harassing, profane, or malicious language
TOXICITY_PATTERNS = [
    r"(?i)\b(kill\s+yourself|die|idiot|stupid|moron|dumbass)\b",
    r"(?i)\b(hate\s+you|fuck|shit|bitch|bastard|asshole)\b",
    r"(?i)\b(sabotage|destroy\s+everything|wipe\s+database|nuke\s+cluster)\b",
    r"(?i)\b(malicious|exploit\s+vulnerability|ransomware|backdoor)\b",
]


class ToxicityScanResult(BaseModel):
    """Result of toxicity scan on text."""

    is_toxic: bool = Field(..., description="Whether toxic content was detected.")
    flagged_terms: list[str] = Field(
        default_factory=list, description="Terms or patterns triggered."
    )
    sanitized_text: str = Field(..., description="Sanitized text if toxic, or original text.")
    reason: str | None = Field(default=None, description="Explanation if flagged.")


class ToxicityGuardrail:
    """Detects abusive, toxic, or malicious language in inputs and outputs."""

    def __init__(self, patterns: list[str] | None = None):
        self.patterns = [re.compile(p) for p in (patterns or TOXICITY_PATTERNS)]

    def scan_text(self, text: str) -> ToxicityScanResult:
        """Scan string for toxic patterns."""
        if not text:
            return ToxicityScanResult(is_toxic=False, sanitized_text="")

        flagged: list[str] = []
        for pattern in self.patterns:
            matches = pattern.findall(text)
            if matches:
                flagged.extend([str(m) for m in matches])

        if flagged:
            logger.warning("Toxicity detected: flagged terms %s", flagged)
            return ToxicityScanResult(
                is_toxic=True,
                flagged_terms=flagged,
                sanitized_text="[REDACTED: TOXIC CONTENT DETECTED]",
                reason=f"Toxic or abusive language detected: {', '.join(set(flagged))}",
            )

        return ToxicityScanResult(
            is_toxic=False,
            flagged_terms=[],
            sanitized_text=text,
            reason=None,
        )

    def scan_alert(self, alert: dict[str, Any]) -> ToxicityScanResult:
        """Scan free-text fields in alert for toxicity."""
        note = str(alert.get("on_call_note", ""))
        return self.scan_text(note)

    def scan_output(self, steps: list[str]) -> ToxicityScanResult:
        """Scan generated steps for toxicity."""
        combined = " ".join(steps)
        return self.scan_text(combined)


_toxicity_guardrail: ToxicityGuardrail | None = None


def get_toxicity_guardrail() -> ToxicityGuardrail:
    """Get or create singleton ToxicityGuardrail."""
    global _toxicity_guardrail
    if _toxicity_guardrail is None:
        _toxicity_guardrail = ToxicityGuardrail()
    return _toxicity_guardrail
