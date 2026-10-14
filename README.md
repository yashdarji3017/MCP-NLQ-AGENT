<h1 align="center">DataQuery AI</h1>

<p align="center">
  A production-grade, enterprise <strong>Natural Language to SQL Assistant</strong> powered by
  <strong>PydanticAI</strong>, <strong>Google Gemini</strong>, <strong>FastMCP</strong>, and <strong>FastAPI</strong>,
  featuring dynamic schema discovery, programmatic AST SQL validation, interactive visualizations, and agent-only Logfire observability.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.111+-009688.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/PydanticAI-2.56+-E92063.svg" alt="PydanticAI">
  <img src="https://img.shields.io/badge/FastMCP-4.1+-7952B3.svg" alt="FastMCP">
  <img src="https://img.shields.io/badge/Google_Gemini-1.5_Flash-4285F4.svg" alt="Google Gemini">
  <img src="https://img.shields.io/badge/PostgreSQL-15+-336791.svg" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Streamlit-1.35+-FF4B4B.svg" alt="Streamlit">
  <img src="https://img.shields.io/badge/Logfire-Observability-FFA000.svg" alt="Logfire">
  <img src="https://img.shields.io/badge/uv-Package_Manager-purple.svg" alt="uv">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
</p>

---

## Overview

DataQuery AI is a modern, full-stack agentic intelligence platform designed to enable business stakeholders to query relational PostgreSQL databases in natural language with strict safety boundaries, verifiable AST guardrails, and automated visualizations.

The platform is architected into four decoupled tiers:

- **FastAPI Gateway** — High-performance REST API orchestrating query ingestion, health checks, schema discovery endpoints, and structured response contracts.
- **PydanticAI Agent Layer** — Autonomous reasoning agent powered by Google Gemini, utilizing structured output schemas, intelligent tool selection, and domain-aware heuristics.
- **FastMCP Microservice** — Standardized Model Context Protocol (MCP) server running on `streamable-http` transport, exposing database schema exploration, SQL validation, and read-only query execution.
- **Streamlit Frontend** — Decoupled analyst dashboard featuring natural language input, interactive Plotly visualization generation, tabular data viewing, schema catalog inspection, and execution timeline diagnostics.

---

## Features

### 🔍 Dynamic Schema Discovery & Reflection
- Live runtime database introspection via SQLAlchemy `inspect(engine)` — eliminating static, brittle schema definitions
- Automatic detection of new tables, altered columns, foreign key relations, primary keys, and nullable types
- Thread-safe TTL schema caching with manual and programmatic `refresh_schema_cache()` triggers
- Automatic redaction of sensitive columns (e.g. password hashes, secret tokens, private API keys)
- Semantic keyword-based schema search (`search_schema`) to prevent LLM prompt context bloat

### 🛡️ Multi-Tier SQL Safety Perimeter
- Programmatic Abstract Syntax Tree (AST) analysis powered by `sqlglot`
- Strict read-only enforcement: permits only single `SELECT` statements (blocks `INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `TRUNCATE`, `EXEC`)
- Blacklisted table protection (e.g., `refresh_tokens`, `password_reset_tokens` blocked at the AST level)
- Automated `LIMIT` clause injection and row count capping to safeguard database resources
- Database session-level read-only transactions (`SET TRANSACTION READ ONLY`) with strict statement timeouts (5000ms)

### 🤖 PydanticAI Agent Reasoning
- Native structured output guarantees with Pydantic v2 schemas (`NLQResponse`)
- Domain-aware intelligence (e.g., rank heuristics where `rank = 1` is highest, sorting `ORDER BY rank ASC`; `is_deleted = false` soft delete filtering; `opportunity_score DESC`)
- Autonomous tool execution via FastMCP protocol bridge (`search_schema`, `get_database_schema`, `get_table_sample`, `validate_sql`, `execute_sql`)
- Plain-English natural language summaries and automated chart recommendations based on query result shape

### 🔌 Streamable HTTP Model Context Protocol (MCP)
- Standardized FastMCP microservice decoupled from core API runtime
- Real-time `streamable-http` transport over SSE/HTTP on port `8001`
- Native session negotiation and lifecycle management via `fastmcp.Client`
- In-process direct tool dispatch fallback in the event of temporary network partitions

### 📊 Decoupled Analyst Dashboard
- Pure HTTP REST-driven Streamlit interface communicating with the FastAPI gateway
- Natural language query input with sample prompt chips for one-click exploration
- Interactive Plotly visualizations (bar charts, line charts, scatter plots) with responsive stretching
- Full execution timeline detailing latency, token metrics, generated SQL, and validation diagnostics
- Live schema browser with column types, nullable flags, primary keys, and foreign key relations

### 📡 Agent-Only Observability & Telemetry
- Targeted Logfire tracing isolated strictly to PydanticAI agent invocations
- Detailed prompt tracking, LLM reasoning spans, tool calls, and completion tokens
- Clean telemetry isolation without noisy HTTP middleware or connection pool poll logs

---

## Tech Stack

### AI & Agent Framework
| Technology | Purpose |
|---|---|
| Python 3.12+ | Core runtime |
| PydanticAI 2.56+ | Agentic orchestration, dependency injection, and tool calling |
| Google Gemini 1.5 Flash | Large Language Model for NL-to-SQL translation |
| FastMCP 4.1+ | Model Context Protocol server and client implementation |
| Pydantic v2 | Strict schema validation and structured output serialization |

### Backend & Microservices
| Technology | Purpose |
|---|---|
| FastAPI | Asynchronous REST API gateway |
| Uvicorn | ASGI web application server |
| HTTPX | Asynchronous HTTP client for MCP communication |
| Logfire | Agent-level distributed tracing and LLM token monitoring |
| uv | Fast Python package management and dependency resolution |

### Database & Security Guardrails
| Technology | Purpose |
|---|---|
| PostgreSQL 15+ | Relational data warehouse |
| SQLAlchemy 2.0 | Connection pooling, session management, and live schema reflection |
| Psycopg 3 | High-performance binary PostgreSQL driver |
| sqlglot | Robust SQL AST parsing, validation, and sanitization |

### Frontend & Analytics
| Technology | Purpose |
|---|---|
| Streamlit 1.35+ | Interactive analyst web application |
| Plotly | Interactive charting (line, bar, scatter) |
| Pandas | In-memory tabular data manipulation and formatting |

---

## Project Structure

```text
NLQ_Agent/
├── src/
│   └── dataquery/
│       ├── agent/                   # PydanticAI agent definition & prompts
│       │   ├── agent.py             # Agent initialization, MCP tool bridge, run pipeline
│       │   ├── dependencies.py      # Agent runtime context dependencies
│       │   ├── models.py            # Pydantic structured output models (NLQResponse)
│       │   └── prompts.py           # System prompts, domain heuristics & safety rules
│       ├── api/                     # FastAPI Gateway
│       │   ├── routes.py            # REST endpoints (/query, /schema, /health)
│       │   └── schemas.py           # API request and response contracts
│       ├── database/                # Database layer & schema reflection
│       │   ├── connection.py        # SQLAlchemy engine & read-only session pool
│       │   ├── executor.py          # Safe read-only SQL execution engine
│       │   ├── metadata.py          # SchemaManager for metadata orchestration
│       │   └── schema_definitions.py# Dynamic reflection, TTL cache & sensitive filter
│       ├── mcp/                     # FastMCP Microservice
│       │   ├── client.py            # FastMCP native client with HTTP session management
│       │   ├── security.py          # FastMCP authorization headers & tokens
│       │   ├── server.py            # FastMCP streamable-http server on port 8001
│       │   └── tools.py             # MCPToolRegistry (schema search, validation, execution)
│       ├── sql/                     # Security, AST parsing & sanitization
│       │   ├── policy.py            # Table/column access policies & blacklists
│       │   ├── sanitizer.py         # Whitespace cleaning & injection protection
│       │   └── validator.py         # sqlglot AST verification & SELECT enforcement
│       ├── config.py                # Environment settings & configuration models
│       ├── main.py                  # Entry points for API, MCP, and UI launchers
│       └── telemetry.py             # Agent-only Logfire telemetry initialization
│
├── frontend/
│   └── app.py                       # Decoupled Streamlit dashboard (Port 8501)
│
├── docs/                            # Architecture documentation & diagrams
├── .env.example                     # Environment variable template
├── pyproject.toml                   # Python project dependencies & metadata
├── uv.lock                          # Dependency lockfile
└── README.md                        # Documentation
```

---

## Getting Started

### Prerequisites

- **Python 3.12+**
- **PostgreSQL 15+** (running locally or accessible via network)
- **uv** (recommended) or **pip**
- **Google Gemini API Key**
- **Logfire Token** (optional, for LLM tracing)

Install **uv**:

```bash
pip install uv
```

---

## Installation & Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd NLQ_Agent
```

### 2. Create & Activate Virtual Environment

```bash
uv venv
```

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

### 3. Install Dependencies

```bash
uv sync
```

Alternatively, using standard pip:
```bash
pip install -e .
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Populate the configuration variables (using your real credentials):

```env
# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/app_db

# Google Gemini LLM
GOOGLE_API_KEY=your_google_api_key_here
GEMINI_MODEL=gemini-1.5-flash

# Model Context Protocol (MCP) Server
MCP_TRANSPORT=streamable-http
MCP_HOST=0.0.0.0
MCP_PORT=8001
MCP_PATH=/mcp
MCP_SERVER_URL=http://localhost:8001/mcp

# FastAPI Gateway Configuration
API_HOST=0.0.0.0
API_PORT=8000

# Streamlit Frontend Configuration
STREAMLIT_PORT=8501
BACKEND_API_URL=http://localhost:8000

# Observability (Agent-Only Logfire Tracing)
LOGFIRE_TOKEN=your_logfire_token_here
```

---

## Running the Services

DataQuery AI consists of three interconnected services. Launch them in separate terminal sessions:

### Service 1: FastMCP Tool Server

Runs the streamable-http MCP server hosting database tools on port `8001`:

```bash
python -m dataquery.mcp.server
```
*Health check available at: `http://localhost:8001/health`*

### Service 2: FastAPI Gateway

Runs the primary REST API service on port `8000`:

```bash
uvicorn dataquery.main:api_app --host 0.0.0.0 --port 8000 --reload
```
*Interactive Swagger API documentation available at: `http://localhost:8000/docs`*

### Service 3: Streamlit Analytics UI

Runs the interactive analyst dashboard on port `8501`:

```bash
streamlit run frontend/app.py --server.port 8501
```
*Dashboard accessible at: `http://localhost:8501`*

---

## Architecture

```
┌────────────────────────────────────────────────────────┐
│               Streamlit Web Dashboard                  │
│       (NLQ Query Bar, Plotly Charts, Schema Catalog)   │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP / REST (/query, /schema)
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Gateway                     │
│         (Request Validation, JSON Schemas, CORS)       │
└───────────────────────────┬────────────────────────────┘
                            │ Agent Pipeline Invocation
┌───────────────────────────▼────────────────────────────┐
│                PydanticAI Agent Layer                  │
│           (Google Gemini 1.5 Flash Reasoning)          │
│    ┌──────────────────────────────────────────────┐    │
│    │ Logfire Telemetry (Agent-Only Token Tracing) │    │
│    └──────────────────────────────────────────────┘    │
└───────────────────────────┬────────────────────────────┘
                            │ FastMCP Protocol (streamable-http)
┌───────────────────────────▼────────────────────────────┐
│                  FastMCP Tool Server                   │
│        (Port 8001 — Streamable HTTP Transport)         │
│  ┌───────────────────┐        ┌─────────────────────┐  │
│  │   search_schema   │        │ get_database_schema │  │
│  ├───────────────────┤        ├─────────────────────┤  │
│  │   validate_sql    │        │     execute_sql     │  │
│  └─────────┬─────────┘        └──────────┬──────────┘  │
└────────────┼─────────────────────────────┼─────────────┘
             │                             │
             ▼                             ▼
┌─────────────────────────┐   ┌──────────────────────────┐
│   sqlglot AST Parser    │   │  SQLAlchemy DB Pool      │
│  - SELECT-Only Policy   │   │  - Dynamic Reflection    │
│  - Table Blacklisting   │   │  - SET READ ONLY Mode    │
│  - LIMIT Auto-Clamping  │   │  - 5000ms Timeout Limit  │
└─────────────────────────┘   └────────────┬─────────────┘
                                           │
                                           ▼
                              ┌──────────────────────────┐
                              │   PostgreSQL Database    │
                              └──────────────────────────┘
```

---

## 6-Stage Execution Pipeline

1. **Natural Language Input** — The user poses an analytical query (e.g., *"Show the top 5 ranking apps for the keyword 'SEO Optimizer'"*).
2. **Schema Grounding** — The agent queries `search_schema` or `get_database_schema` to identify relevant tables, primary/foreign keys, and data types without exceeding context windows.
3. **Structured SQL Synthesis** — Google Gemini synthesizes an optimized SQL statement incorporating domain rules (`ORDER BY rank ASC`, active filters, etc.).
4. **AST Safety Verification** — The SQL string passes through `validate_sql` where `sqlglot` validates statement boundaries, verifies table permissions, and enforces row capping.
5. **Read-Only Execution** — `execute_sql` dispatches the query through a read-only transaction session (`SET TRANSACTION READ ONLY`) bounded by strict statement timeouts.
6. **Insight & Visualization** — The agent generates an executive plain-English summary, tabular result set, and visualization recommendations (chart type, X/Y axes) rendered natively in Streamlit.

---

## Logging & Observability

- **Agent-Only Isolation**: Telemetry via `Agent.instrument_all()` specifically monitors PydanticAI reasoning and Gemini LLM executions.
- **Trace Context**: Captures complete system prompts, user inputs, tool call arguments, output responses, execution latencies, and token consumption metrics.
- **Noise Elimination**: Standard FastAPI access endpoints, database connection heartbeats, and MCP ping traffic are isolated from the agent telemetry stream to maintain clean trace logs.

---

