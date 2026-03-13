# Zabbix AI Alert System

A unified system for Zabbix alerts using Google GenAI or OpenAI with a Blockchain Infrastructure Specialist persona.

## Setup

1.  Configure the `.env` file in this directory (use `.env.example` as a template).
2.  Install requirements: `pip install -r requirements.txt`.

## Available Versions

### 1. Standalone Scripts (`genai_alert.py` / `openai_alert.py`)
Simple Python scripts for direct Zabbix integration using either Gemini or OpenAI.
- **Usage**: `./genai_alert.py -m "{JSON_DATA}"` or `./openai_alert.py -m "{JSON_DATA}"`
- **Output**: Generates a `.txt` file in the same directory.

### 2. Dockerized API (`docker/`)
A full FastAPI implementation with additional features.
- **Usage**: `docker-compose up -d` (inside the `docker/` directory).
- **Features**: SQLite persistence, HTML navigation dashboard at `/outputs`, SIEM/Graylog enrichment.
- **Output**: Stored in DB and/or local files.

## Shared Logic

Both versions share the same core engines (`genai_engine.py` / `openai_engine.py`) and SIEM fetching module (`siem_fetching.py`), ensuring consistent analysis regardless of how you deploy it.

## Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `AI_PROVIDER` | Model provider: `gemini` or `openai`. | `gemini` |
| `DEFAULT_PROMPT` | Custom persona or context prompt. | - |
| `GOOGLE_API_KEY` | Your Google Gemini API Key. | **Required for gemini** |
| `GENAI_MODEL` | The Gemini model to use. | `gemini-pro` |
| `OPENAI_API_KEY` | Your OpenAI API Key. | **Required for openai** |
| `OPENAI_MODEL` | The OpenAI model to use. | `gpt-4o-mini` |
| `GENAI_OUTPUT_TYPE` | (Docker only) `FILE`, `DB`, or `BOTH`. | `BOTH` |
| `GRAYLOG_ENABLED` | Enable SIEM enrichment. | `false` |
| `GENAI_MAX_OUTPUTS` | (Docker only) Retention limit. | `0` (Disabled) |

For detailed instructions on the Docker version, see [docker/README.md](./docker/README.md)