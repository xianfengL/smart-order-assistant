# Validation record

Date: 2026-09-18

## Verified locally

- Python 3.12.14; isolated virtual environment.
- SQLite demo with actual LangGraph checkpoint persistence, Chroma persistent vector retrieval, Argon2/JWT authentication and SSE.
- Backend tests: 19 passed after corrections; one upstream Starlette deprecation warning.
- LangChain tool-calling Agent exercised with a deterministic model and actual permission-filtered SQL tool.
- Browser smoke check passed: login, chart rendering, graph follow-up, policy sources, persisted history and mobile overflow; screenshots in docs/screenshots.
- Included MCP server exercised through an actual stdio client/server protocol exchange.
- Vue production build succeeds; first load JavaScript approximately 94 kB before gzip, chart module loaded on demand.
- npm dependency audit reports zero known vulnerabilities.
- ECharts updated to 6.1.0 following a vulnerability in older releases.

## Not established by these checks

- Real model and embedding vendor responses: no API key supplied.
- Docker images and PostgreSQL container runtime: Docker unavailable locally. A CI job is provided to run those checks after upload.
- MySQL runtime: connection driver and SQL dialect support provided; no server available for integration testing.
- GitHub upload is complete only when a real repository URL and commit are returned; local files and configuration alone do not establish an upload or public deployment.

The original reference contains a feature description, no source code or design assets. This is an independent implementation of those features.
