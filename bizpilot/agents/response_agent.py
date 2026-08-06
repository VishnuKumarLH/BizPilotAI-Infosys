"""Response Agent: present verified analysis in owner-friendly language."""

from __future__ import annotations

from .schemas import ResponseMetadata
from ..graph.state import AgentWorkflowState, require_state_fields


class BusinessResponseAgent:
    def run(self, state: AgentWorkflowState) -> dict:
        require_state_fields(state, "analysis", "workflow_id")
        analysis = state["analysis"]
        agents = [*state.get("agents_used", []), "response_agent"]
        metadata = ResponseMetadata(
            provider_used=state.get("provider_used", "rule_based"),
            fallback_used=state.get("fallback_used", False),
            confidence=state.get("confidence", 0),
            agents_used=agents,
            tools_used=state.get("tools_used", []),
            workflow_id=state["workflow_id"],
        ).model_dump()
        findings = analysis.get("key_findings", [])
        actions = analysis.get("recommended_actions", [])
        risks = analysis.get("risks", [])
        reasoning = " ".join(analysis.get("reasoning", []))
        summary = (
            f"{findings[0]} {analysis['decision']}" if findings else analysis["decision"]
        )
        response = {
            "summary": summary,
            "key_findings": findings,
            "final_decision": analysis["decision"],
            "recommendations": actions,
            "recommended_actions": actions,
            "risks": risks,
            "avoid_actions": risks,
            "reasoning": reasoning,
            "priority": analysis.get("priority", "medium"),
            "confidence": metadata["confidence"],
            "data_sources": [
                tool.replace("_tool", "").replace("_", " ").title()
                for tool in metadata["tools_used"]
            ],
            "missing_data": state.get("retrieval", {}).get(
                "missing_information", []
            ),
            "provider_used": metadata["provider_used"],
            "ai_provider": metadata["provider_used"],
            "fallback_used": metadata["fallback_used"],
            "agents_used": agents,
            "tools_used": metadata["tools_used"],
            "workflow_id": metadata["workflow_id"],
            "warnings": state.get("warnings", []),
            "execution_steps": [
                *state.get("execution_trace", []),
                "Response Agent",
            ],
        }
        final_response = self._format_text(response)
        return {
            "response": response,
            "final_response": final_response,
            "agents_used": agents,
            "execution_trace": response["execution_steps"],
        }

    @staticmethod
    def _format_text(response: dict) -> str:
        sections = [
            "Summary\n" + response["summary"],
            "Recommended Decision\n" + response["final_decision"],
        ]
        if response["key_findings"]:
            sections.append(
                "Key Findings\n"
                + "\n".join(f"- {item}" for item in response["key_findings"])
            )
        if response["recommended_actions"]:
            sections.append(
                "Recommended Actions\n"
                + "\n".join(
                    f"{index}. {item}"
                    for index, item in enumerate(
                        response["recommended_actions"], start=1
                    )
                )
            )
        if response["risks"]:
            sections.append(
                "Risks or Limitations\n"
                + "\n".join(f"- {item}" for item in response["risks"])
            )
        sections.append(f"Confidence\n{round(response['confidence'] * 100)}%")
        sections.append(
            "Agents and Tools Used\n"
            + ", ".join(response["agents_used"])
            + ("\n" + ", ".join(response["tools_used"]) if response["tools_used"] else "")
        )
        return "\n\n".join(sections)
