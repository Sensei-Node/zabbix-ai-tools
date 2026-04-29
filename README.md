ZABBIX AI TOOLS
---------------

This repository contains a suite of AI-powered integrations and tools designed to enhance Zabbix monitoring capabilities through Generative AI and the Model Context Protocol (MCP).

## Project Structure

The repository is organized into two main component projects:

### 1. [zabbix-mcp-server](./zabbix-mcp-server)
An implementation of a Model Context Protocol (MCP) server for Zabbix. It allows AI models to interact directly with Zabbix data through a standardized interface.
- **Key Files**: `Dockerfile`, `docker-compose.yml`, `src/`
- **Port**: 8000 (default)

### 2. [zabbix-genai-insights](./zabbix-genai-insights)
A toolset for analyzing Zabbix alerts using Generative AI with SIEM (Graylog) enrichment. Supports multiple LLM providers.
- **Key Files**: `genai_alert.py`, `genai_engine.py`, `llm_provider.py`, `siem_fetching.py`
- **Docker**: Located in `./zabbix-genai-insights/docker`
- **Supported LLM Providers**: Google Gemini, OpenAI (GPT-4o), DeepSeek, Ollama (local models)
- **SIEM Integration**: Graylog log correlation with deduplication and statistical summaries

---

## CI/CD & Deployment

The repository uses GitHub Actions for automated builds and pushes to Amazon ECR. The workflows are decoupled to allow independent maintenance of each component.

### Workflows
- **Build and Push MCP Server**: Triggers on changes within `zabbix-mcp-server/`.
- **Build and Push GenAI Insights**: Triggers on changes within `zabbix-genai-insights/`.

### Required GitHub Secrets
To run the CI/CD pipelines, the following secrets must be configured in the repository:
- `AWS_ACCESS_KEY_ID`: AWS access key for ECR authentication.
- `AWS_SECRET_ACCESS_KEY`: AWS secret key.
- `AWS_REGION`: The AWS region (e.g., `us-east-1`).
- `REGISTRY_URL_MCP`: The ECR repository URL for the MCP server.
- `REGISTRY_URL_GENAI`: The ECR repository URL for the GenAI Insights API.

---

## Usage

Each project contains its own `docker-compose.yml` for local development. Refer to the specific project directories for detailed setup instructions.
