# Zabbix GenAI Alert API (Docker Version)

This directory contains the dockerized version of the GenAI alert system, providing a FastAPI-based web service for processing Zabbix alerts with multi-provider LLM support.

## Features

- **Multi-Provider LLM**: Switch between Gemini, OpenAI, DeepSeek, or Ollama via environment variables.
- **Asynchronous Processing**: Immediate `202 Accepted` response to prevent Zabbix webhook timeouts.
- **SQLite Persistence**: Stores generated insights with status tracking (`PENDING`, `COMPLETED`, `ERROR`).
- **HTML Dashboard**: Browse insights at `/outputs` with status badges and search.
- **Graylog SIEM Enrichment**: Automatic log correlation with deduplication and statistical summaries.
- **Structured Prompts**: Chain-of-thought prompt engineering for consistent, actionable output.
- **Retention Policy**: Automatic pruning via `GENAI_MAX_OUTPUTS`.

## Project Structure

| File | Description |
| :--- | :--- |
| `app.py` | FastAPI routes, background task orchestration, environment configuration |
| `db.py` | SQLite persistence layer with WAL mode for concurrency |
| `html_template.tpl` | HTML/CSS template for the `/outputs` dashboard |
| `Dockerfile` | Container build definition |
| `docker-compose.yml` | Orchestration with volume mounts for data persistence |

The Docker version also leverages shared modules from the parent directory:

| Module | Description |
| :--- | :--- |
| `genai_engine.py` | Core analysis engine with structured prompt building |
| `llm_provider.py` | Multi-provider LLM abstraction (Gemini, OpenAI, DeepSeek, Ollama) |
| `siem_fetching.py` | Graylog log search, deduplication, and summarization |

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

HTML dashboard listing all generated insights with status badges.

### `GET /outputs/{event_id}`

Retrieve a specific insight as plain text.

### `GET /health`

Health check with provider and configuration details.

```json
{
  "status": "ok",
  "provider": "gemini",
  "model": "gemini-pro",
  "output_type": "BOTH",
  "graylog_enabled": false
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
