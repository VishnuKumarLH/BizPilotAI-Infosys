# BizPilot AI

BizPilot AI is an explainable multi-agent decision assistant for a small retail business. It combines products, sales, expenses, customer feedback, configured local weather, short-term conversation context, and reusable decision memory into traceable recommendations.

This repository implements Infosys Springboard **Milestones 1, 2, and 3**. It deliberately does not include Milestone 4 automation or Milestone 5 deployment features.

## Milestone 3 features

- A Coordinator controlling a real LangGraph workflow.
- Four genuinely separated agents: Planning, Research and Retrieval, Analysis and Decision, and Response.
- Typed shared state plus validated Pydantic agent outputs.
- Standardized, observable business tools with graceful individual failure handling.
- Gemini → Groq → verified rule-based fallback.
- Session-backed short-term memory for follow-up questions.
- SQL-backed, searchable, deduplicated long-term decision memory.
- Workflow history with plan, evidence, decision, warnings, agent steps, and tool timings.
- Authenticated workflow and memory REST APIs.
- Updated Decision Center, Agent History, and Memory pages.

## Agent architecture

```mermaid
flowchart LR
    Q[Owner request] --> C[Coordinator]
    C --> P[Planning Agent]
    P --> R[Research Agent]
    R --> A[Analysis & Decision Agent]
    A --> F[Response Agent]
    F --> O[Owner-ready recommendation]
    C <--> S[(Short-term memory)]
    C <--> L[(Long-term memory)]
    R --> T[Business tools]
    O --> H[(Workflow history)]
```

The Coordinator creates `AgentWorkflowState`, loads memory, classifies the request, and invokes the graph. Agents communicate only through structured state. SQLAlchemy records are converted to JSON-safe dictionaries before entering the workflow.

## Supported demonstrations

- “Which products should I restock?”
- “How is my business performing this month?”
- “What are customers complaining about?”
- “What offer should I provide based on Madurai weather?”
- “Which product should I promote?” followed by “Why did you choose that?”
- “What did you recommend previously for low-stock products?”
- “Calculate profit margin for revenue 50000 and expenses 32000.”

## Requirements

- Python 3.11 or later (tested with Python 3.13)
- PostgreSQL 14+ for the target setup
- PowerShell commands below for Windows
- Gemini and Groq keys are optional

SQLite remains supported by `TestConfig` and can be used for a lightweight local demonstration.

## Install on Windows

### 1. Create and activate the virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

### 2. Configure the environment

```powershell
Copy-Item .env.example .env
```

Edit `.env`. Never commit real keys or secrets.

Important values:

```env
FLASK_APP=app.py
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
```

For a local SQLite demonstration, use:

```env
DATABASE_URL=sqlite:///bizpilot.db
```

### 3. Start PostgreSQL (optional Docker helper)

```powershell
docker compose up -d db
```

### 4. Apply the schema safely

```powershell
flask --app app db upgrade
```

The Milestone 3 migration adds tables and one nullable trace column. It does not drop existing tables or data.

### 5. Add demonstration data

```powershell
python seed_data.py
```

To replace only the existing demo account and its owned records:

```powershell
python seed_data.py --reset
```

Demo login:

```text
Email: demo@stylehub.com
Password: demo123
```

### 6. Run the server

```powershell
flask --app app run --debug
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000).

## Run tests

```powershell
python -m pytest -q
```

External AI providers and weather are mocked where required. The suite uses an isolated in-memory test database and does not depend on live internet.

## Demonstration flow

1. Open **AI Decision Center** and ask “Which products should I restock?”
2. Expand **Agent workflow** to show Coordinator → Planning → Research → Analysis and Decision → Response.
3. Point out the tools, provider, fallback state, confidence percentage, and workflow UUID.
4. Ask “Which product should I promote?”, then ask “Why did you choose that?” in the same session to demonstrate short-term memory.
5. Ask “What did you recommend previously for low-stock products?” to demonstrate long-term memory retrieval.
6. Open **Agent History** to show the stored plan, evidence, decision, agent steps, and tool durations.
7. Open **Memory** to search long-term decisions and view recent session messages.
8. Leave AI keys blank (or mock provider failure in tests) to demonstrate the clear rule-fallback notice without breaking the workflow.

## Provider behavior

1. Gemini is attempted first and retried according to `AI_MAX_RETRIES`.
2. Groq is attempted if Gemini is missing, unavailable, misconfigured, or returns invalid structured output.
3. Deterministic evidence-backed rules complete the analysis when providers fail.

Only the Analysis and Decision Agent calls an AI provider. Invalid JSON receives one conservative repair attempt, then the provider fallback continues. Provider exceptions and secrets are never shown in owner-facing responses.

## Main routes

| Area | Routes |
|---|---|
| Decision Center | `GET /`, `POST /chat/send` |
| Workflow API | `POST /api/agent/run`, `GET /api/agent/workflows`, `GET /api/agent/workflows/<workflow_id>` |
| Memory API | `GET /api/memory`, `GET /api/memory/search`, memory delete/clear routes |
| History and Memory UI | `GET /agent-history`, `GET /memory` |
| Business modules | CRUD under `/products/`, `/sales/`, `/expenses/`, and `/feedback/` |
| Weather proxy | `GET /tools/weather` |
| Authentication | routes under `/auth/` |

All business, workflow, and memory routes require authentication and enforce current-user ownership.

## Database additions

- `agent_workflow_runs`: workflow-level plan, evidence, analysis, decision, metadata, and timing.
- `agent_memories`: long-term decision memory with uniqueness, confidence, importance, and usage fields.
- `tool_call_logs`: sanitized input/status/output summary/error/duration for every tool call.
- `agent_execution_log.workflow_id`: nullable link from existing agent steps to a workflow UUID.

Short-term memory reuses existing `chat_sessions` and `chat_messages` rather than duplicating conversation tables.

## Project structure

```text
bizpilot/
├── agents/       # classifier, four specialized agents, coordinator, schemas, prompts
├── graph/        # typed shared state and LangGraph construction
├── tools/        # standardized tool registry
├── services/     # AI, weather, memory, workflow, confidence, validation
├── routes/       # auth, APIs, chat, history/memory, business CRUD
├── templates/    # Decision Center, Agent History, Memory, CRUD and auth pages
├── static/       # responsive CSS, JavaScript, images
└── models.py     # business, workflow, tool-log, and memory models
migrations/       # Alembic schema history
tests/            # unit and integration tests
docs/             # audit, architecture, and test report
```

## Documentation

- [Milestones 1 and 2 audit](docs/MILESTONE_1_2_AUDIT.md)
- [Milestone 3 architecture](docs/MILESTONE_3_ARCHITECTURE.md)
- [Milestone 3 test report](docs/MILESTONE_3_TEST_REPORT.md)

## Scope and limitations

- Weather recommendations support the location configured in `.env`; no geocoding service is included.
- Profit is an operating estimate from recorded sales and expenses, not audited net profit.
- Long-term memory uses transparent SQL text matching, not embeddings or a vector database.
- AI provider quality and availability depend on external services; deterministic fallback remains available.
- No Milestone 4 autonomous execution/background jobs or Milestone 5 cloud deployment was added.
