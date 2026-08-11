# BizPilot AI

BizPilot AI is an explainable multi-agent decision assistant for a small retail business. It combines products, sales, expenses, customer feedback, configured local weather, short-term conversation context, and reusable decision memory into traceable recommendations.

This repository implements Infosys Springboard **Milestones 1, 2, 3, and 4**. Milestone 4 extends the existing system with workflow lifecycle tracking, monitoring APIs, dashboard metrics, production configuration, Docker support, and Google Cloud Run readiness.

## Milestone 4 Features

- Coordinator-controlled real LangGraph workflow.
- Four separated agents: Planning, Research and Retrieval, Analysis and Decision, and Response.
- Validated structured state and Pydantic agent outputs.
- Request-aware tool selection with isolated tool failures.
- Gemini -> Groq -> verified rule-based fallback.
- Session-backed short-term memory for follow-up questions.
- SQL-backed, searchable, deduplicated long-term decision memory.
- Workflow history with lifecycle events, plan, evidence, decision, validation warnings, agent steps, and tool timings.
- Real metrics for workflows, agents, tools, durations, partial runs, failures, and fallback usage.
- Authenticated workflow, memory, timeline, tool, agent, and metrics REST APIs.
- Safe public health endpoint.
- Docker and Cloud Run deployment readiness.

## Milestone 4 Architecture

```mermaid
flowchart LR
    Q[Owner request] --> C[Coordinator]
    C <--> S[(Short-term memory)]
    C <--> L[(Long-term memory)]
    C --> P[Planning Agent]
    P --> R[Research and Retrieval Agent]
    R --> T[Business tools]
    T --> A[Analysis and Decision Agent]
    A --> V[Validation]
    V --> F[Response Agent]
    F --> O[Owner-ready recommendation]
    O --> H[(Workflow history)]
    H --> M[Metrics and dashboard]
```

The Coordinator creates `AgentWorkflowState`, loads memory, classifies the request, and invokes the graph. Agents communicate only through structured state. SQLAlchemy records are converted to JSON-safe dictionaries before entering the workflow.

## Workflow Automation

Supported demonstrations include:

- "Which products should I restock?"
- "Which product should I promote?" followed by "Why did you choose that?"
- "What did you recommend previously for low-stock products?"
- "How is my business performing this month?"
- "What offer should I provide based on Madurai weather?"
- "Calculate profit margin for revenue 50000 and expenses 32000."

The workflow selects relevant tools instead of calling every tool for every request.

## Memory Lifecycle

SHORT-TERM MEMORY:

`chat_sessions` and `chat_messages`

Purpose: current and recent conversation context. Example: "Why did you choose that?"

LONG-TERM MEMORY:

`agent_memories`

Purpose: reusable historical business decisions and observations. Example: "What did you recommend previously for low-stock products?"

WORKFLOW HISTORY:

`agent_workflow_runs`, `agent_execution_log`, and `tool_call_logs`

Purpose: traceability and observability of workflow executions.

## Monitoring

Agent History shows workflow totals, success rate, partial and failed counts, fallback usage, per-agent execution counts, per-tool call counts, failures, and average durations from stored logs.

## API Layer

| Area | Routes |
|---|---|
| Decision Center | `GET /`, `POST /chat/send` |
| Workflow API | `POST /api/agent/run`, `GET /api/agent/workflows`, `GET /api/agent/workflows/<workflow_id>` |
| Observability | `GET /api/health`, `GET /api/metrics`, `GET /api/workflows/<workflow_id>/timeline`, `GET /api/workflows/<workflow_id>/tools`, `GET /api/workflows/<workflow_id>/agents` |
| Memory API | `GET /api/memory`, `GET /api/memory/search`, memory delete/clear routes |
| History and Memory UI | `GET /agent-history`, `GET /memory` |
| Business modules | CRUD under `/products/`, `/sales/`, `/expenses/`, and `/feedback/` |
| Weather proxy | `GET /tools/weather` |
| Authentication | routes under `/auth/` |

All business, workflow, metrics, and memory routes require authentication and enforce current-user ownership. `/api/health` is intentionally public and returns only safe service status.

## Requirements

- Python 3.11 or later
- PostgreSQL 14+ for production
- Gemini and Groq keys are optional
- SQLite remains supported for tests and lightweight local demos

## Install On Windows

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
flask --app app db upgrade
python seed_data.py
flask --app app run
```

Demo login:

```text
Email: demo@stylehub.com
Password: demo123
```

## Production Environment Variables

```env
FLASK_APP=app.py
FLASK_DEBUG=false
SECRET_KEY=replace-with-a-long-random-value
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/bizpilot
GEMINI_API_KEY=
GROQ_API_KEY=
PRIMARY_AI_PROVIDER=gemini
FALLBACK_AI_PROVIDER=groq
ENABLE_RULE_BASED_FALLBACK=true
AI_REQUEST_TIMEOUT=30
AI_MAX_RETRIES=1
WEATHER_LATITUDE=9.9252
WEATHER_LONGITUDE=78.1198
WEATHER_LOCATION=Madurai
SHORT_TERM_MEMORY_LIMIT=8
LONG_TERM_MEMORY_LIMIT=5
PORT=8080
```

Never commit `.env`.

## Docker

```powershell
docker build -t bizpilot-ai .
docker run --rm -p 8080:8080 --env-file .env -e PORT=8080 bizpilot-ai
```

The container uses Gunicorn and binds to `0.0.0.0:${PORT}` for Cloud Run compatibility.

## Google Cloud Run Deployment

See [Milestone 4 deployment](docs/MILESTONE_4_DEPLOYMENT.md).

## Testing

```powershell
python -m pytest -q
```

External AI providers and weather are mocked where required. The suite uses an isolated in-memory test database and does not depend on live internet.

## Documentation

- [Milestones 1 and 2 audit](docs/MILESTONE_1_2_AUDIT.md)
- [Milestone 3 architecture](docs/MILESTONE_3_ARCHITECTURE.md)
- [Milestone 3 test report](docs/MILESTONE_3_TEST_REPORT.md)
- [Milestone 4 architecture](docs/MILESTONE_4_ARCHITECTURE.md)
- [Milestone 4 Cloud Run deployment](docs/MILESTONE_4_DEPLOYMENT.md)

## Scope And Limitations

- Weather recommendations support the configured location only; no geocoding service is included.
- Profit is an operating estimate from recorded sales and expenses, not audited net profit.
- Long-term memory uses transparent SQL text matching, not embeddings or a vector database.
- AI provider quality and availability depend on external services; deterministic fallback remains available.
- Milestone 4 is deployment-ready, but this repository does not claim a live Cloud Run deployment has been executed.
