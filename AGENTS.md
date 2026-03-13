# AI Agent Guidelines

This document serves as a guide for AI assistants (Agents) working on the `zabbix-ai-tools` repository. 

## 🏗 Repository Architecture

This is a mono-repo containing independent but related Zabbix AI tools.

### Key Directories
- **`zabbix-mcp-server/`**: Python-based MCP server. Follows standard MCP patterns.
- **`zabbix-genai-insights/`**: Alert analysis engine. Uses FastAPI for the internal API (located in `docker/app.py`).
- **`.github/workflows/`**: Contains specialized YAML files for CI. Avoid merging these into a single file to maintain build independence.

## 🛠 Development Patterns

### Docker & ECR
- Always use `${REGISTRY_URL}` in `docker-compose.yml` to support dynamic environment tagging.
- The build process relies on the `IMAGE_TAG` environment variable (defaults to `latest`).

### CI/CD Logic
- Changes are detected per-directory. When adding new files, ensure they are within the scope of the respective workflow's `paths` filter.
- Use `aws_cleanup.sh` after pushes to prune untagged images in ECR.

### Dependencies
- Each project manages its own `requirements.txt` or `pyproject.toml`.
- Avoid adding global dependencies to the root of the repository unless they apply to the entire suite.

## 📝 Documentation Rules
- Keep the root `README.md` updated with architecture changes.
- Document any new Secrets required for the CI/CD process.
