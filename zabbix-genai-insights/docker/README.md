# Zabbix GenAI Alert API (Docker Version)

This directory contains the dockerized version of the GenAI alert system, providing a FastAPI-based web service for processing Zabbix alerts with multi-provider LLM support.

## Features

- **Multi-Provider LLM**: Switch between Gemini, OpenAI, DeepSeek, or Ollama via environment variables.
- **Contextual Memory**: Queries historical insights from SQLite to detect recurring patterns and cross-host correlations.
- **MCP Enrichment**: Optional integration with the Zabbix MCP Server to fetch live host details, active problems, and recent events — providing real-time Zabbix context to the LLM.
- **Asynchronous Processing**: Immediate `202 Accepted` response to prevent Zabbix webhook timeouts.
- **SQLite Persistence**: Stores generated insights with status tracking (`PENDING`, `COMPLETED`, `ERROR`).
- **HTML Dashboard**: Browse insights at `/outputs` with status badges and search.
- **Graylog SIEM Enrichment**: Automatic log correlation with deduplication and statistical summaries.
- **Structured Prompts**: Chain-of-thought prompt engineering for consistent, actionable output.
- **Retention Policy**: Automatic pruning via `GENAI_MAX_OUTPUTS`.
- **Non-blocking Enrichment**: Both SIEM and MCP enrichment are fault-tolerant — if either service is unavailable, insights are generated normally without that context.

## Project Structure

| File | Description |
| :--- | :--- |
| `app.py` | FastAPI routes, background task orchestration, environment configuration |
| `db.py` | SQLite persistence layer with WAL mode for concurrency |
| `html_template.tpl` | HTML/CSS template for the `/outputs` listing dashboard |
| `html_detail.tpl` | HTML/CSS template for the individual insight detail view |
| `Dockerfile` | Container build definition |
| `docker-compose.yml` | Orchestration with volume mounts for data persistence |

The Docker version also leverages shared modules from the parent directory:

| Module | Description |
| :--- | :--- |
| `genai_engine.py` | Core analysis engine with structured prompt building, contextual memory, and non-blocking enrichment orchestration |
| `llm_provider.py` | Multi-provider LLM abstraction (Gemini, OpenAI, DeepSeek, Ollama) |
| `siem_fetching.py` | Graylog log search, deduplication, and summarization |
| `mcp_fetching.py` | Zabbix MCP Server integration — live host, problem, and event data via MCP SSE protocol |

## Contextual Memory

The Docker version leverages SQLite to provide **contextual memory** across alerts:

- **Host-level recurrence**: Before analyzing a new alert, the engine queries the last 5 insights for the same host. If the host has been alerting repeatedly, the LLM factors this into severity assessment and recommendations.
- **Cross-host correlation**: The engine also fetches the last 10 alerts across all hosts from the past 60 minutes. If multiple hosts are alerting concurrently, the LLM can identify systemic or network-level failures.
- **Graceful degradation**: In standalone CLI mode (no DB), memory is silently skipped — no configuration needed.

## Prerequisites

- Docker and Docker Compose
- At least one LLM API key (Google, OpenAI, or DeepSeek) — or a running Ollama instance for local models

## Setup

1. Configure the `.env` file in the parent directory (use `.env.example` as a template).
2. Build and start the container:
   ```bash
   docker-compose up -d --build
   ```

## API Endpoints

### `POST /analyze`

Submit a Zabbix alert for AI analysis. Returns immediately with `202 Accepted`.

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "EVENT_ID": "12345",
    "HOST": "web-server-01",
    "TRIGGER_NAME": "High CPU usage",
    "TRIGGER_SEVERITY": "High",
    "ITEM_VALUE": "95.2%"
  }'
```

**Response:**
```json
{
  "status": "accepted",
  "event_id": "12345",
  "provider": "openai",
  "model": "gpt-4o",
  "message": "Analysis started in background"
}
```

### `GET /outputs`

HTML dashboard listing all generated insights. Features:
- **Stats bar** with counters for total, completed, pending, and error insights
- **Search** by host, trigger name, event ID, or any text in the card
- **Filter buttons** to show only completed, pending, or error insights
- **Rich cards** showing trigger name, host, severity (color-coded dot), item value, timestamp, and event ID
- **Auto-refresh** when pending items exist (polls every 8 seconds)

### `GET /outputs/{event_id}`

Styled detail page for a single insight. Features:
- Full insight text with metadata header (host, severity, timestamp, status)
- Auto-refresh with spinner animation for pending insights
- Back navigation to the listing dashboard

### `GET /health`

Health check with provider and configuration details.

```json
{
  "status": "ok",
  "provider": "gemini",
  "model": "gemini-pro",
  "output_type": "BOTH",
  "graylog_enabled": false,
  "mcp_enabled": false
}
```

## Environment Variables

### LLM Provider Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | LLM backend: `gemini`, `openai`, `deepseek`, `ollama` | `gemini` |
| `LLM_MODEL` | Model name (provider-specific) | `gemini-pro` |
| `GOOGLE_API_KEY` | Google Gemini API key | — |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `DEEPSEEK_API_KEY` | DeepSeek API key | — |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `GENAI_MODEL` | Legacy alias for `LLM_MODEL` (backward compatible) | `gemini-pro` |
| `GENAI_PROMPT` | Custom prompt override | *(structured default)* |

### Output & Retention

| Variable | Description | Default |
| :--- | :--- | :--- |
| `GENAI_OUTPUT_TYPE` | Storage target: `FILE`, `DB`, or `BOTH` | `BOTH` |
| `GENAI_MAX_OUTPUTS` | Max insights to keep (0 = unlimited) | `0` |

### Graylog SIEM Enrichment

| Variable | Description | Default |
| :--- | :--- | :--- |
| `GRAYLOG_ENABLED` | Enable log enrichment from Graylog | `false` |
| `GRAYLOG_URL` | Base URL of your Graylog instance | — |
| `GRAYLOG_TOKEN` | API token for Graylog authentication | — |
| `GRAYLOG_SEARCH_MINUTES` | Search window in minutes | `30` |
| `GRAYLOG_SEARCH_LIMIT` | Max log entries to fetch per query | `100` |
| `GRAYLOG_VERIFY_SSL` | Verify SSL certificates for Graylog | `false` |

### MCP (Zabbix MCP Server)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `MCP_ENABLED` | Enable live Zabbix enrichment via MCP Server | `false` |
| `ZABBIX_MCP_URL` | MCP Server SSE endpoint URL | `http://zabbix-mcp:8000/sse` |
| `MCP_TIMEOUT` | Timeout in seconds for MCP requests | `15` |

## Graylog Enrichment Details

When `GRAYLOG_ENABLED=true`, the system:

1. Extracts the hostname from the Zabbix alert's `HOST` field (strips IP suffixes)
2. Queries Graylog for matching logs within the configured time window
3. Filters out noise (`kernel`, `sshd`, `CRON`, `systemd`) at the query level
4. **Deduplicates** repeated log entries to reduce token usage
5. Generates a **statistical summary** (message count by application and source)
6. Formats everything and injects it into the LLM prompt as correlated evidence

This enrichment gives the AI model real operational context, significantly improving root cause analysis accuracy.

## Persistence

- **Database**: `./data/genai_insights.db` (SQLite with WAL mode)
- **Files**: `./outputs/{event_id}.txt`

Storage behavior is controlled by `GENAI_OUTPUT_TYPE`.

## Zabbix Integration

1. Import the Media Type template: [zabbix-mediatype-genai-webhook.yml](../zabbix-mediatypes/zabbix-mediatype-genai-webhook.yml)
2. Configure the `url` parameter to point to `http://your-server:8000/analyze`
3. Add the Media Type to your notification User
