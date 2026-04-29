# Zabbix GenAI Alert System

A unified system for analyzing Zabbix alerts using Generative AI with SIEM (Graylog) enrichment. Supports multiple LLM providers including Google Gemini, OpenAI, DeepSeek, and local models via Ollama.

## Architecture

```
┌──────────┐     ┌──────────────┐     ┌───────────────┐     ┌─────────────┐
│  Zabbix   │────▶│ genai_engine │────▶│ llm_provider  │────▶│ Gemini /    │
│  Alert    │     │   (core)     │     │ (abstraction) │     │ OpenAI /    │
└──────────┘     └──────┬───────┘     └───────────────┘     │ DeepSeek /  │
                        │                                    │ Ollama      │
                        ▼                                    └─────────────┘
                 ┌──────────────┐
                 │siem_fetching │
                 │  (Graylog)   │
                 └──────────────┘
```

### Shared Modules

| Module | Description |
| :--- | :--- |
| `genai_engine.py` | Core analysis engine — builds structured prompts, orchestrates SIEM enrichment, calls the LLM |
| `llm_provider.py` | Multi-provider abstraction layer — factory pattern for switching between LLM backends |
| `siem_fetching.py` | Graylog integration — log search, deduplication, statistical summary |

Both the standalone CLI and the Docker API share these modules, ensuring consistent analysis regardless of deployment mode.

## Setup

1. Copy `.env.example` to `.env` and configure your provider and API key.
2. Install requirements: `pip install -r requirements.txt`

## Available Versions

### 1. Standalone Script (`genai_alert.py`)

A CLI tool for direct Zabbix integration via Media Types.

```bash
./genai_alert.py -m '{"HOST": "web01", "TRIGGER_NAME": "High CPU", "TRIGGER_SEVERITY": "High"}'
```

Output: Generates a `.txt` file in the same directory.

### 2. Dockerized API (`docker/`)

A full FastAPI implementation with persistence, dashboard, and background processing.

```bash
cd docker/
docker-compose up -d --build
```

Features: SQLite persistence, HTML dashboard at `/outputs`, SIEM/Graylog enrichment, background processing.

For detailed Docker instructions, see [docker/README.md](./docker/README.md).

## Multi-Provider LLM Support

The system supports multiple LLM providers through a unified abstraction layer (`llm_provider.py`). Switch providers by changing environment variables — no code changes required.

### Supported Providers

| Provider | `LLM_PROVIDER` | API Key Variable | Example Models |
| :--- | :--- | :--- | :--- |
| Google Gemini | `gemini` | `GOOGLE_API_KEY` | `gemini-pro`, `gemini-1.5-pro` |
| OpenAI | `openai` | `OPENAI_API_KEY` | `gpt-4o`, `gpt-4o-mini` |
| DeepSeek | `deepseek` | `DEEPSEEK_API_KEY` | `deepseek-chat`, `deepseek-reasoner` |
| Ollama (local) | `ollama` | *(none)* | `llama3`, `mistral`, `codellama` |

### Quick Start Examples

**Using OpenAI:**
```bash
export LLM_PROVIDER=openai
export LLM_MODEL=gpt-4o
export OPENAI_API_KEY=sk-...
```

**Using DeepSeek:**
```bash
export LLM_PROVIDER=deepseek
export LLM_MODEL=deepseek-chat
export DEEPSEEK_API_KEY=sk-...
```

**Using Ollama (local, no API key):**
```bash
export LLM_PROVIDER=ollama
export LLM_MODEL=llama3
export OLLAMA_BASE_URL=http://localhost:11434
```

## Contextual Memory

When running in Docker mode (with SQLite persistence), the engine automatically queries the insights database before each analysis to build historical context:

### Host-Level Memory
- Retrieves the last 5 completed insights for the same host
- Injects trigger names, severities, timestamps, and insight excerpts into the prompt
- Allows the LLM to detect **recurring patterns** (e.g. "this host has had 3 CPU alerts in the last hour") and escalate severity accordingly

### Cross-Host Correlation
- Retrieves the last 10 alerts across all hosts from the past 60 minutes
- Filters out the current host (already covered above) and presents concurrent alerts on other hosts
- Enables the LLM to identify **systemic failures** (e.g. "3 hosts in the same cluster are alerting simultaneously — likely a network or upstream issue")

### Graceful Degradation
- In standalone CLI mode (`genai_alert.py`), the DB module is not available
- The engine catches the import error silently and proceeds without historical context
- No configuration needed — memory is automatic when the DB is present

## Structured Prompt Engineering

The default prompt uses a chain-of-thought structure to produce consistent, actionable insights:

1. **Summary** — One-line incident description
2. **Root Cause Analysis** — Probable cause based on available data
3. **Severity Assessment** — Critical / High / Medium / Low with justification, factoring in recurrence and cross-host patterns
4. **Correlated Evidence** — Highlights from SIEM logs (when available)
5. **Historical Pattern** — Describes recurrence, escalation, or novelty based on memory
6. **Recommended Actions** — Concrete resolution steps
7. **Prevention** — Measures to avoid recurrence

The prompt can be overridden via the `GENAI_PROMPT` environment variable.

## SIEM Enrichment (Graylog)

When `GRAYLOG_ENABLED=true`, the system automatically:

1. Searches Graylog for logs matching the alert's host
2. Deduplicates repeated log entries
3. Generates a statistical summary (message count by application/source)
4. Formats the data and injects it into the LLM prompt as correlated evidence

This gives the AI model real operational context beyond the alert metadata alone.

## Environment Variables

### LLM Configuration

| Variable | Description | Default |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | LLM backend: `gemini`, `openai`, `deepseek`, `ollama` | `gemini` |
| `LLM_MODEL` | Model name (provider-specific) | `gemini-pro` |
| `GOOGLE_API_KEY` | Google Gemini API key | — |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `DEEPSEEK_API_KEY` | DeepSeek API key | — |
| `OLLAMA_BASE_URL` | Ollama server URL | `http://localhost:11434` |
| `GENAI_MODEL` | Legacy alias for `LLM_MODEL` | `gemini-pro` |
| `GENAI_PROMPT` | Custom prompt override | *(structured default)* |

### Output (Docker Only)

| Variable | Description | Default |
| :--- | :--- | :--- |
| `GENAI_OUTPUT_TYPE` | `FILE`, `DB`, or `BOTH` | `BOTH` |
| `GENAI_MAX_OUTPUTS` | Retention limit (0 = unlimited) | `0` |

### Graylog / SIEM

| Variable | Description | Default |
| :--- | :--- | :--- |
| `GRAYLOG_ENABLED` | Enable SIEM enrichment | `false` |
| `GRAYLOG_URL` | Graylog base URL | — |
| `GRAYLOG_TOKEN` | Graylog API token | — |
| `GRAYLOG_SEARCH_MINUTES` | Log search window in minutes | `30` |
| `GRAYLOG_SEARCH_LIMIT` | Max log entries to fetch | `100` |
| `GRAYLOG_VERIFY_SSL` | Verify SSL certificates | `false` |
