"""Realistic LLM Stub Service for benchmarking and load testing (D6).

Replaces live external LLM API calls with fixed responses returned after a realistic delay,
allowing load testing to benchmark system queuing, retrieval, and serialization without
being throttled by provider rate limits.
"""

import time
from typing import Any

from pydantic import BaseModel

from src.agent.state import InvestigationOutput, TriageHandOff
from src.gateway.client import LiteLLMGateway, set_llm_gateway


class StubLLMService:
    """Provides deterministic stub responses for LLM invocations with simulated latency."""

    def __init__(self, simulated_delay_seconds: float = 0.05):
        self.simulated_delay = simulated_delay_seconds

    def handle_mock_call(self, prompt: str, response_model: type[BaseModel]) -> BaseModel:
        """Return realistic canned instance of response_model after simulated delay."""
        if self.simulated_delay > 0:
            time.sleep(self.simulated_delay)

        if response_model == TriageHandOff:
            return TriageHandOff(
                alert_name="StubAlert",
                primary_cause_class="saturation",
                candidate_cause_classes=["saturation", "configuration"],
                extracted_entities={"metrics": {"disk_utilization": 85.0}},
                reasoning_summary="Synthetic triage reasoning for load testing.",
                suggested_queries=["replication slot WAL accumulation"],
                prompt_version="stub-triage-v1.0.0",
            )

        if response_model == InvestigationOutput:
            return InvestigationOutput(
                cause_class="saturation",
                first_response_steps=[
                    "1. Check pg_replication_slots for inactive slots.",
                    "2. Select pg_drop_replication_slot('standby_1') if orphaned.",
                ],
                citations=[],
                severity="SEV2",
                severity_basis="Replication slot WAL retention causes disk saturation.",
                route="self-serve runbook",
                verified=True,
                escalation_reason=None,
                trace=["Stub: Investigation completed successfully."],
                retrieved_passages=[],
                prompt_version="stub-investigator-v1.0.0",
            )

        # Fallback dynamic mock
        fields = response_model.model_fields
        dummy_data: dict[str, Any] = {}
        for fname, f_info in fields.items():
            if f_info.annotation is str or f_info.annotation == str:
                dummy_data[fname] = "stub_string"
            elif (
                f_info.annotation is list or getattr(f_info.annotation, "__origin__", None) is list
            ):
                dummy_data[fname] = []
            elif (
                f_info.annotation is dict or getattr(f_info.annotation, "__origin__", None) is dict
            ):
                dummy_data[fname] = {}
            elif f_info.annotation is bool:
                dummy_data[fname] = True
            elif f_info.annotation in [int, float]:
                dummy_data[fname] = 0
            else:
                dummy_data[fname] = None

        return response_model.model_validate(dummy_data)


def install_stub_llm(simulated_delay: float = 0.05) -> None:
    """Wire singleton LiteLLMGateway to use the StubLLMService."""
    stub = StubLLMService(simulated_delay_seconds=simulated_delay)
    gateway = LiteLLMGateway(mock_handler=stub.handle_mock_call)
    set_llm_gateway(gateway)
