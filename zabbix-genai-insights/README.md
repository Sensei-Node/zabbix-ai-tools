# Zabbix AI Alert System

A unified system for Zabbix alerts using Google GenAI, OpenAI, or DeepSeek with a Blockchain Infrastructure Specialist persona.

## Setup

1.  Configure the `.env` file in this directory (use `.env.example` as a template).
2.  Install requirements: `pip install -r requirements.txt`.

## Available Versions

### 1. Unified Standalone Script (`ai_insights.py`)
A single Python script for direct Zabbix integration that supports Google Gemini, OpenAI, and DeepSeek.
- **Usage**: `./ai_insights.py -m "{JSON_DATA}"`
- **Configuration Hierarchy** (Priority):
    1. Command line arguments (`-k`, `-model`).
    2. Payload keys (`AI_API_KEY`, `AI_MODEL`).
    3. Unified environment variables (`AI_API_KEY`, `AI_MODEL`).
    4. Provider-specific variables (`GOOGLE_API_KEY`, `OPENAI_API_KEY`, etc.).
- **Output**: Generates a `.txt` file in the same directory.

- **Features**: SQLite persistence, HTML navigation dashboard at `/outputs`, SIEM/Graylog enrichment, Perennial Memory (Mem0).
- **Output**: Stored in DB and/or local files.

## Shared Logic

Both versions share the same core engines (`genai_engine.py` / `openai_engine.py` / `dsk_engine.py`) and SIEM fetching module (`siem_fetching.py`). They also share a single **`requirements.txt`** file at the root.

The Docker version additionally utilizes `memory_manager.py` for long-term (perennial) context, ensuring consistent analysis regardless of how you deploy it.

## Environment Variables

| Variable | Description | Default |
| :--- | :--- | :--- |
| `AI_PROVIDER` | Model provider: `gemini`, `openai`, or `deepseek`. | `gemini` |
| `AI_API_KEY` | Unified API Key (overrides provider specific keys). | - |
| `AI_MODEL` | Unified Model Name (overrides provider specific models). | - |
| `DEFAULT_PROMPT` | Custom persona or context prompt. | - |
| `GOOGLE_API_KEY` | Your Google Gemini API Key. | **Required for gemini** |
| `GENAI_MODEL` | The Gemini model to use. | `gemini-pro` |
| `OPENAI_API_KEY` | Your OpenAI API Key. | **Required for openai** |
| `OPENAI_MODEL` | The OpenAI model to use. | `gpt-4o-mini` |
| `DEEPSEEK_API_KEY` | Your DeepSeek API Key. | **Required for deepseek** |
| `DEEPSEEK_MODEL` | The DeepSeek model to use. | `deepseek-chat` |
| `OUTPUT_TYPE` | (Docker only) `FILE`, `DB`, or `BOTH`. | `BOTH` |
| `GRAYLOG_ENABLED` | Enable SIEM enrichment. | `false` |
| `MAX_OUTPUTS` | (Docker only) Retention limit. | `0` (Disabled) |
| `MEMORY_ENABLED` | (Docker only) Enable perennial memory (Mem0). | `false` |
| `MEM0_DIR` | (Docker only) Path for perennial memory storage. | `/app/data/mem0` |

For detailed instructions on the Docker version, see [docker/README.md](./docker/README.md)