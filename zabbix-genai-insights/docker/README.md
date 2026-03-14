# Zabbix AI Alert API (Docker Version)

This directory contains the dockerized version of the AI alert system, providing a FastAPI-based web service for processing Zabbix alerts using Gemini or OpenAI.

## Features

- **Asynchronous Processing**: Immediate `202 Accepted` response to prevent timeouts.
- **SQLite Persistence**: Stores generated insights with status tracking (`PENDING`, `COMPLETED`).
- **HTML Listing UI**: Beautiful dashboard at `/outputs` with status badges.
- **Graylog SIEM Enrichment**: Shared core logic with filtering.
- **Retention Policy**: Automatic pruning (`GENAI_MAX_OUTPUTS`).

## Project Structure

This directory is organized into modular components to ensure maintainability and high performance:

- **`app.py`**: The core API layer. Handles FastAPI routes, background task orchestration, and environment configuration.
- **`db.py`**: The data persistence layer. Contains all SQLite logic, including WAL mode configuration, connection handling, and optimized queries.
- **`html_template.tpl`**: The visual layer. A standalone HTML/CSS template for the `/outputs` dashboard, separate from the application logic.
- **`Dockerfile` & `docker-compose.yml`**: Containerization and orchestration logic.

The Docker version also leverages shared modules from the root directory (`genai_engine.py`, `openai_engine.py` and `siem_fetching.py`) to ensure consistency with the standalone script version.

## Prerequisites

- Docker and Docker Compose.
- Google Gemini API Key or OpenAI API Key.
- (Optional) Graylog API Token.

## Setup

1.  Configure the `.env` file in the parent directory (or use `.env.example` as a base).
2.  Build and start the container:
    ```bash
    docker-compose up -d --build
    ```

## Usage

### Processing Alerts (POST)
You can submit alerts to the `/analyze` endpoint. The API accepts `AI_PROVIDER` and `API_KEY` in the payload to override the default environment variables.

**Example using default settings (from .env):**
```bash
curl -X POST "http://localhost:8000/analyze" \
     -H "Content-Type: application/json" \
     -d '{"EVENT_ID": "12345", "NAME": "High CPU Load", "HOST": "server-01"}'
```

**Example overriding the provider to OpenAI with a custom API Key:**
```bash
curl -X POST "http://localhost:8000/analyze" \
     -H "Content-Type: application/json" \
     -d '{
           "EVENT_ID": "12346", 
           "NAME": "High CPU Load", 
           "HOST": "server-01", 
           "AI_PROVIDER": "openai", 
           "API_KEY": "sk-your-openai-api-key"
         }'
```

### Retrieval API (GET)
- **Listing Page**: `http://localhost:8000/outputs` (HTML dashboard)
- **Specific Insight**: `GET /outputs/{event_id}` (Raw text)

**Example to retrieve a specific insight:**
```bash
curl -X GET "http://localhost:8000/outputs/12346"
```

### Zabbix Configuration
1.  Import the Media Type template: [zabbix-mediatype-genai-webhook.yml](./zabbix-mediatype-genai-webhook.yml).
2.  Configure the `url` parameter (e.g., `http://your-server:8000/analyze`).
3.  Add the Media Type to your User.

## Environment Variables

### Core Configuration
| Variable | Description | Default |
| :--- | :--- | :--- |
| `AI_PROVIDER` | `gemini` or `openai`. | `gemini` |
| `DEFAULT_PROMPT` | Custom persona or context prompt for the AI. | Professional Blockchain Specialist |
| `GOOGLE_API_KEY` | Your Google Gemini API Key. | **Required for gemini** |
| `GENAI_MODEL` | The Gemini model to use for analysis. | `gemini-pro` |
| `OPENAI_API_KEY` | Your OpenAI API Key. | **Required for openai** |
| `OPENAI_MODEL` | The OpenAI model to use. | `gpt-4o-mini` |
| `GENAI_OUTPUT_TYPE` | Storage target: `FILE`, `DB`, or `BOTH`. | `BOTH` |
| `GENAI_MAX_OUTPUTS` | Max number of insights to keep (0 for unlimited). | `0` |

### Graylog SIEM Enrichment
| Variable | Description | Default |
| :--- | :--- | :--- |
| `GRAYLOG_ENABLED` | Enable log enrichment from Graylog. | `false` |
| `GRAYLOG_URL` | Base URL of your Graylog instance. | - |
| `GRAYLOG_TOKEN` | API Token for Graylog authentication. | - |
| `GRAYLOG_SEARCH_MINUTES` | Search window in minutes for recent logs. | `30` |

### Zabbix MCP Server Integration
| Variable | Description | Default |
| :--- | :--- | :--- |
| `MCP_ENABLED` | Enable fetching context from Zabbix MCP Server. | `false` |
| `ZABBIX_MCP_URL` | Base SSE URL of the Zabbix MCP Server instance. | `http://zabbix-mcp:8000/sse` |

## Graylog Enrichment

To enable Graylog support, set `GRAYLOG_ENABLED=true` in `.env`.
The system will search for logs matching the `HOST` field from Zabbix, automatically removing any IP suffix.
Exclusion filters for `kernel`, `sshd`, `CRON`, and `systemd` are applied at the query level for efficiency.

## Zabbix MCP Server Integration

To enable MCP support, set `MCP_ENABLED=true` in `.env` and specify the `ZABBIX_MCP_URL`.
The system connects to the MCP Server using Server-Sent Events (SSE). It exposes the server's tools (like fetching hosts, items, and problems) to the AI as native function calls. The AI dynamically decides if it needs to execute those actions to understand the alert better.

## Persistence

Insights are stored in `./data/genai_insights.db` and as `.txt` files in `./outputs/` depending on the `GENAI_OUTPUT_TYPE` setting.
