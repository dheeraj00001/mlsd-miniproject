"""Output Authorization & Remediation Defense Filter (L4, guardrails.md).

Enforces:
1. Advisory Invariant: System strictly produces diagnostic advisory guidance and NEVER executes remediation.
2. Output Authorization Filter: Validates categorical enum bounds (cause_class, severity, route).
3. Blocks and flags dangerous remediation commands (e.g. rm -rf, drop database, sudo) within generated steps.
"""

import logging
import re

from pydantic import BaseModel, Field

from src.agent.state import InvestigationOutput

logger = logging.getLogger(__name__)

ALLOWED_CAUSE_CLASSES = {
    "saturation",
    "contention",
    "configuration",
    "dependency_failure",
    "data_volume",
}

ALLOWED_SEVERITIES = {"SEV1", "SEV2", "SEV3", "SEV4"}

ALLOWED_ROUTING_TARGETS = {
    "self-serve runbook",
    "page-secondary",
    "incident-commander",
}

# Dangerous remediation command patterns that must never be recommended unconditionally or executed
DESTRUCTIVE_COMMAND_PATTERNS = [
    r"(?i)\brm\s+-(rf?|fr?)\b",
    r"(?i)\bdrop\s+database\b",
    r"(?i)\bdrop\s+table\b",
    r"(?i)\btruncate\s+table\b",
    r"(?i)\bformat\s+[a-z]:\b",
    r"(?i)\bmkfs(\.[a-z0-9]+)?\b",
    r"(?i)\bkill\s+-9\s+\d+\b",
    r"(?i)\bsudo\s+(reboot|shutdown|init\s+0)\b",
    r"(?i)\bchmod\s+777\b",
    r"(?i)\bdd\s+if=/dev/\b",
]


class OutputFilterResult(BaseModel):
    """Result of output authorization and safety validation."""

    is_authorized: bool = Field(..., description="Whether output passed all authorization checks.")
    violations: list[str] = Field(default_factory=list, description="List of policy violations.")
    sanitized_output: InvestigationOutput | None = Field(
        default=None, description="Authorized and sanitized output."
    )


class OutputAuthorizationFilter:
    """Validates and enforces boundaries on model outputs before return."""

    def __init__(self, destructive_patterns: list[str] | None = None):
        self.destructive_patterns = [
            re.compile(p) for p in (destructive_patterns or DESTRUCTIVE_COMMAND_PATTERNS)
        ]

    def authorize_output(self, output: InvestigationOutput) -> OutputFilterResult:
        """Validate output structure, categorical enums, and check for destructive remediation commands."""
        violations: list[str] = []

        # 1. Check cause class
        if output.cause_class not in ALLOWED_CAUSE_CLASSES:
            violations.append(
                f"Unauthorized cause class '{output.cause_class}'. Must be one of {ALLOWED_CAUSE_CLASSES}"
            )

        # 2. Check severity
        if output.severity not in ALLOWED_SEVERITIES:
            violations.append(
                f"Unauthorized severity '{output.severity}'. Must be one of {ALLOWED_SEVERITIES}"
            )

        # 3. Check route
        if output.route not in ALLOWED_ROUTING_TARGETS:
            violations.append(
                f"Unauthorized route '{output.route}'. Must be one of {ALLOWED_ROUTING_TARGETS}"
            )

        # 4. Check steps for destructive commands
        sanitized_steps: list[str] = []
        for step in output.first_response_steps:
            flagged = False
            for pat in self.destructive_patterns:
                if pat.search(step):
                    violations.append(
                        f"Prohibited destructive remediation pattern detected in step: {pat.pattern}"
                    )
                    flagged = True
                    break
            if flagged:
                sanitized_steps.append("[BLOCKED: PROHIBITED REMEDIATION COMMAND REMOVED]")
            else:
                sanitized_steps.append(step)

        if violations:
            logger.warning(
                "Output authorization filter flagged %d violation(s): %s",
                len(violations),
                violations,
            )
            return OutputFilterResult(
                is_authorized=False,
                violations=violations,
                sanitized_output=None,
            )

        output.first_response_steps = sanitized_steps
        return OutputFilterResult(
            is_authorized=True,
            violations=[],
            sanitized_output=output,
        )


_output_filter: OutputAuthorizationFilter | None = None


def get_output_filter() -> OutputAuthorizationFilter:
    """Get or create singleton OutputAuthorizationFilter."""
    global _output_filter
    if _output_filter is None:
        _output_filter = OutputAuthorizationFilter()
    return _output_filter
