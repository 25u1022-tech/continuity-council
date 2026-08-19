# Deployment

## Render.com

1. Create a **New Web Service** from the repository.
2. Select **Docker** as the runtime.
3. Use the repository `Dockerfile`; it serves the built React UI and FastAPI API from one service on port `8000`.
4. Add these environment variables:
   - `CLICKHOUSE_HOST`
   - `CLICKHOUSE_PORT` (`8443`)
   - `CLICKHOUSE_USER`
   - `CLICKHOUSE_PASSWORD`
   - `CLICKHOUSE_DATABASE` (`continuity_council`)
   - `GEMINI_API_KEY`
5. Set the health check path to `/api/health`.
6. Deploy, then run the ClickHouse seed and MCP proof from a controlled environment with the same credentials when preparing the demo.

The free Render tier sleeps when idle, which can interrupt a live judging flow. Use the cheapest paid plan during the judging window so the service stays warm and responsive.