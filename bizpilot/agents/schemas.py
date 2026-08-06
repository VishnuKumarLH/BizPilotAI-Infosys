"""Validated structured outputs for the Milestone 3 specialized agents."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class PlanningOutput(BaseModel):
    intent: str
    objective: str
    required_tools: list[str] = Field(default_factory=list)
    steps: list[str] = Field(min_length=1)
    expected_output: str
    tool_parameters: dict[str, dict[str, Any]] = Field(default_factory=dict)


class RetrievalOutput(BaseModel):
    evidence: dict[str, Any] = Field(default_factory=dict)
    tool_results: dict[str, Any] = Field(default_factory=dict)
    tools_used: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    retrieval_status: Literal["complete", "partial", "failed"]


class AnalysisOutput(BaseModel):
    decision: str
    confidence: float = Field(ge=0, le=1)
    key_findings: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    reasoning: list[str] = Field(default_factory=list)
    priority: Literal["high", "medium", "low"] = "medium"

    @field_validator("decision")
    @classmethod
    def decision_must_exist(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("decision cannot be empty")
        return value.strip()


class ResponseMetadata(BaseModel):
    provider_used: str
    fallback_used: bool
    confidence: float = Field(ge=0, le=1)
    agents_used: list[str]
    tools_used: list[str]
    workflow_id: str
