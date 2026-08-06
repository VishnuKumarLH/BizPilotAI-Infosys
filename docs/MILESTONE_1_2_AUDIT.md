# Milestones 1 and 2 Audit

Audit date: 3 August 2026

Scope: the existing BizPilot AI repository was inspected before Milestone 3 work. Working authentication, CRUD, chat, provider, weather, database, and UI code was retained. Repairs were limited to prerequisites that Milestone 3 uses.

## Existing architecture reviewed

- Flask application factory in `bizpilot/__init__.py`, with SQLAlchemy, Flask-Migrate, and Flask-Login extensions.
- PostgreSQL-compatible SQLAlchemy models (JSONB variants) with SQLite test/development compatibility.
- Authenticated product, sales, expense, feedback, chat-session, and weather routes.
- Existing Coordinator, Orchestrator, Retriever, Decision, and Response pipeline.
- Gemini/Groq HTTP provider service and deterministic decision rules.
- Responsive HTML/CSS/JavaScript Decision Center and CRUD pages.
- Initial Alembic migration, deterministic seed script, and 29-test baseline suite.

The baseline suite passed before changes: **29 passed**.

## Milestone 1 audit

| Requirement | Current status | Existing implementation | Problem found | Fix performed | Final status |
|---|---|---|---|---|---|
| Python and Flask environment | Complete | Application factory, `.venv`, pinned Flask dependencies | None required | Preserved | Complete |
| Database configuration | Complete | SQLAlchemy URI from `DATABASE_URL`; PostgreSQL driver; SQLite test config | `.env.example` default did not reflect the internship PostgreSQL target | PostgreSQL example restored while keeping SQLite test compatibility | Fixed |
| Environment-variable configuration | Complete | `config.py`, `.env.example`, secret file ignored | Memory limits were not configurable | Added short/long memory limits | Fixed |
| LangChain/LangGraph integration | Missing | Existing pipeline was ordered Python calls only | Milestone 3 explicitly requires graph orchestration | Added LangGraph 1.2.10 and a typed four-node `StateGraph` | Fixed |
| Foundational request agent | Complete | `CoordinatorAgent` validates/classifies common business prompts with confidence | “complaining” wording was not classified as feedback | Added complaint variants and retained deterministic classification | Fixed |
| Structured agent output | Partially Complete | LLM decision JSON was validated manually | Planning, retrieval, analysis, and response contracts were not independently validated | Added Pydantic schemas and typed shared state | Fixed |
| Reusable prompt templates | Partially Complete | One grounded decision prompt existed inside `decision.py` | Prompt text was embedded in the agent | Centralized grounding and output templates in `agents/prompts.py` | Fixed |
| Basic interaction workflow | Complete | Chat route ran five ordered stages and persisted traces | State was a collection of disconnected dictionaries | Added shared `AgentWorkflowState` and state validation | Fixed |
| Testing interface | Complete | AI Decision Center, `/chat/send`, and automated tests | No workflow-level REST API | Added `POST /api/agent/run` without removing chat compatibility | Fixed |
| Empty/oversized input | Complete | Route rejects empty and >2,000-character prompts | None | Reused in the new API | Complete |
| Missing API keys and provider errors | Complete | Missing keys led to deterministic rules | Fallback detail was not workflow-level | Added provider/fallback state and owner-friendly warnings | Fixed |
| Invalid LLM JSON | Partially Complete | Invalid JSON was rejected and retried | No conservative JSON repair attempt | Added one bounded object-extraction repair before fallback | Fixed |
| Database failure handling | Complete | Transaction rollback and safe HTTP errors | Workflow persistence was spread across the route | Centralized atomic persistence in `WorkflowService` | Fixed |
| Unsupported questions | Partially Complete | General advice fallback answered every unmatched prompt | Out-of-scope requests were not clearly labelled | Added `unsupported` intent with safe scope guidance | Fixed |

## Milestone 2 audit

| Requirement | Current status | Existing implementation | Problem found | Fix performed | Final status |
|---|---|---|---|---|---|
| Product/inventory lookup | Complete | Retriever queried owned active products and low stock | No explicit out-of-stock tool contract | Added product, low-stock, and out-of-stock registry tools | Fixed |
| Sales summary and product movement | Complete | Revenue, orders, best sellers, and slow movers | Results were returned in several shapes | Wrapped tools in one standard result envelope | Fixed |
| Expense summary | Complete | Period totals and category breakdown | No standard tool error result | Added registry wrapper and telemetry | Fixed |
| Profit calculation | Partially Complete | Rule decision subtracted expenses from revenue | No independently invokable profit tool | Added profit/calculator tools with input validation | Fixed |
| Feedback retrieval and analysis | Partially Complete | Ratings, sentiment, unresolved count, comments | Complaint categories and product mentions were not extracted | Added feedback retrieval and category tools | Fixed |
| Business-profile retrieval | Missing | Profile data existed on `User` | No agent tool exposed it | Added tenant-scoped business profile tool | Fixed |
| Weather utility | Complete | Open-Meteo client with timeout and cache | Results lacked common tool format and unsupported-location handling | Wrapped configured-location weather in registry | Fixed |
| Tool selection | Complete | Orchestrator selected actions from intent | Plan did not expose canonical tool names/parameters | Planning Agent now stores required tools and parameters in state | Fixed |
| Tool response format | Missing | Retriever returned raw data dictionaries | Tools did not share `success/tool_name/data/message/error` | Added consistent tool envelope for every registry call | Fixed |
| Tool error handling | Partially Complete | Retriever skipped failed actions | Exceptions were swallowed and not traceable | Research Agent records missing data/warnings and continues | Fixed |
| Tool monitoring | Missing | Only agent timings were stored | No per-tool input/status/summary/error/duration record | Added `tool_call_logs` model, migration, API, and History UI | Fixed |
| Gemini → Groq → rules fallback | Partially Complete | Retryable Gemini errors used Groq; rules were final fallback | Invalid Gemini credentials stopped before Groq | All configured providers are now attempted in order; verified rules remain final fallback | Fixed |
| Secret-safe logging | Complete | Keys were not logged | No Milestone 3 workflow logger | Added sanitized workflow/agent/tool logging | Fixed |

## Final audit conclusion

Milestones 1 and 2 are complete for the dependencies Milestone 3 requires. Existing working modules were preserved. No Milestone 4 automation, background processing, autonomous execution, deployment, or Milestone 5 infrastructure was added.
