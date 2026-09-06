# ── Stage 1: Build React/CRA frontend ──────────────────────────────────────
FROM node:20-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/yarn.lock ./
RUN corepack enable && yarn install --frozen-lockfile

COPY frontend/ ./
# Empty string = relative /api paths → backend serves frontend from same origin
ENV REACT_APP_BACKEND_URL=
RUN yarn build

# ── Stage 2: Python + Node runtime (Node required for mcp-clickhouse npx) ──
FROM nikolaik/python-nodejs:python3.11-nodejs18-slim

WORKDIR /app

# Install Python dependencies
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# Copy backend source, ClickHouse seeds, and helper scripts
COPY backend/ ./backend/
COPY clickhouse/ ./clickhouse/
COPY scripts/ ./scripts/

# Copy built frontend from stage 1
COPY --from=frontend-build /app/frontend/build ./frontend/build

# Tell the backend where to find the built frontend (CRA outputs to build/)
ENV FRONTEND_BUILD_DIR=../frontend/build

# Cloud Run sets PORT automatically; 8080 is the Cloud Run default
EXPOSE 8080

WORKDIR /app/backend
CMD uvicorn server:app --host 0.0.0.0 --port ${PORT:-8080}
