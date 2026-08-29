# Deployment

## Render.com

### Option A: Backend-Only Deployment (Recommended when Frontend is on Vercel)

1. Create a **New Web Service** from the repository.
2. Select **Docker** as the runtime.
3. Set the **Dockerfile Path** to `Dockerfile.render`.
4. Set the **Docker Context** to the repository root (`.`).
5. Add these environment variables:
   - `CLICKHOUSE_HOST`
   - `CLICKHOUSE_PORT` (`8443`)
   - `CLICKHOUSE_USER`
   - `CLICKHOUSE_PASSWORD`
   - `CLICKHOUSE_DATABASE` (`continuity_council`)
   - `GEMINI_API_KEY`
6. Set the health check path to `/api/health`.
7. Deploy.

### Option B: Unified Fullstack Deployment

1. Create a **New Web Service** from the repository.
2. Select **Docker** as the runtime.
3. Use the default repository `Dockerfile`; it builds the React UI and serves both the SPA and FastAPI backend from port `8000`.
4. Add the same environment variables as above.
5. Set health check to `/api/health`.

The free Render tier sleeps when idle, which can interrupt a live judging flow. Use the cheapest paid plan during the judging window so the service stays warm and responsive.