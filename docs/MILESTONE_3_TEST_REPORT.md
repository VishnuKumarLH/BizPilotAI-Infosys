# Milestone 3 Test Report

Test date: 3 August 2026  
Environment: Python 3.13.0, Flask test client, isolated in-memory SQLite test database  
Command: `python -m pytest -q`  
Final automated result: **45 passed in 45.66 seconds**

External AI and weather calls are mocked or disabled in automated workflow tests. No automated test depends on live internet.

## Automated results

| Test name / group | Purpose | Expected result | Actual result | Status |
|---|---|---|---|---|
| `test_planning_agent_creates_structured_inventory_plan` | Validate inventory intent, objective, steps, tools, and output contract | Valid ranked-restock plan | Required tools and schema returned | Passed |
| `test_planning_agent_extracts_calculation_inputs` | Parse revenue and expenses from a calculator prompt | 50,000 revenue and 32,000 expenses | Both values parsed correctly | Passed |
| `test_tool_registry_returns_consistent_structured_result` | Verify common tool envelope and telemetry | Required five fields plus successful log | Contract and duration verified | Passed |
| `test_research_agent_records_one_tool_failure_without_crashing` | Ensure one failed tool does not stop retrieval | Partial result, warning, other evidence retained | Partial workflow continued | Passed |
| `test_confidence_penalizes_missing_tools_and_rule_fallback` | Verify transparent confidence reductions | Deterministic bounded score | Calculated score matched 0.67 | Passed |
| Foundational classifier tests | Cover stock, sales, offers, expenses, profit, feedback, weather, performance, and advice | Correct deterministic category | All classifications matched | Passed |
| AI provider service tests | Cover Gemini retries, Groq fallback, invalid credentials, timeouts, and output validation | Configured chain followed safely | Gemini → Groq behavior and retry flags verified | Passed |
| `test_long_term_memory_upserts_duplicate_business_decision` | Prevent duplicate long-term memories | Existing intent memory updated | One row remained with latest workflow | Passed |
| `test_memory_rejects_secret_like_content` | Prevent provider-like secrets entering memory | Unsafe memory rejected | No memory object created | Passed |
| Restock integration workflow | Run plan, tools, analysis, response, state, persistence, and logs | Completed inventory workflow | Workflow/evidence/5 steps/tool logs saved | Passed |
| Monthly performance integration workflow | Combine sales, expenses, profit, and product performance | Completed business scorecard workflow | Required evidence and decision saved | Passed |
| Feedback integration workflow | Retrieve comments and complaint categories | Completed feedback workflow | Category tool and persisted evidence verified | Passed |
| Weather recommendation integration workflow | Use mocked Madurai weather with products/sales | Weather-based offer without network | Mocked 35°C result produced cotton recommendation | Passed |
| `test_follow_up_uses_short_term_memory` | Resolve “Why did you choose that?” in one session | Explanation refers to prior decision | Follow-up intent and contextual reason returned | Passed |
| `test_previous_decision_uses_deduplicated_long_term_memory` | Retrieve previous restock decision after repeated analyses | Prior workflow returned; one memory row | Previous decision found; duplicate prevented | Passed |
| `test_empty_and_unsupported_requests_are_safe` | Validate empty and out-of-scope prompts | HTTP 400 for empty; safe supported-scope answer otherwise | Both behaviors matched | Passed |
| `test_workflow_and_memory_apis_enforce_ownership` | Prevent cross-user workflow/memory access | Owner succeeds; other user gets 404 | Tenant isolation verified | Passed |
| Existing chat tests | Preserve sessions, workflow trace, rename/archive/history, weather, and isolation | No regression | All existing chat behaviors passed | Passed |
| Existing CRUD tests | Preserve product, sale, stock rollback, expense, and feedback behavior | No regression | All CRUD and transaction tests passed | Passed |
| Auth and page-render tests | Preserve login/registration and render new History/Memory pages | Authenticated pages render; protected pages redirect | All page/auth assertions passed | Passed |

## Acceptance coverage

| Acceptance behavior | Automated evidence | Status |
|---|---|---|
| Coordinator controls the workflow | Persisted five-step execution log and compiled graph integration | Passed |
| Four specialized agents use shared state | Exact `agents_used` order asserted | Passed |
| Tool selection and genuine evidence | Required tool names and stored evidence asserted | Passed |
| Single tool failure is graceful | Partial-retrieval unit test | Passed |
| Short-term follow-up memory | Two-request same-session integration test | Passed |
| Long-term retrieval and deduplication | Previous-decision integration and upsert unit test | Passed |
| Provider fallback | Provider unit tests plus rule-backed workflow tests | Passed |
| Empty/unsupported input safety | API integration test | Passed |
| Workflow and memory ownership | Cross-user API test | Passed |
| Agent and tool monitoring | Database counts and workflow detail API assertions | Passed |

## Migration verification

The full Alembic chain was applied to a blank temporary SQLite database:

```text
upgrade -> 6632024d16ff (initial schema)
upgrade 6632024d16ff -> 9b4f2a1d7c30 (Milestone 3)
```

Verified tables: `agent_workflow_runs`, `agent_memories`, `tool_call_logs`, and `agent_execution_log`. The temporary validation database was removed afterward.

The same Milestone 3 migration was also applied successfully to the configured PostgreSQL development database without dropping existing data.

## Manual UI verification

The local authenticated application was inspected in the in-app browser:

| Check | Expected result | Actual result | Status |
|---|---|---|---|
| Decision Center navigation | History and Memory links appear within existing theme | Links visible and correctly styled | Passed |
| Recommendation card | Findings, decision, actions, risks, tools, workflow, confidence, and provider visible | All requested sections rendered | Passed |
| Agent History summary | Workflow UUID, intent, status, agents, tools, confidence, provider, fallback, and duration visible | All summary metadata rendered | Passed |
| Expanded workflow details | Plan, evidence counts, decision, warnings, agent steps, and tool durations visible | Details expanded and readable | Passed |
| Memory page | Recent messages, workflow ID, clear action, search, long-term card, tags, importance/confidence/usage visible | All memory components rendered | Passed |
| Browser console | No JavaScript errors | Zero error entries | Passed |

## Final result

Milestone 3 automated, migration, and UI checks passed. The documented limitations are product/business-data completeness, external provider availability, configured-location weather only, operating-profit estimates, and SQL text matching rather than vector search.
