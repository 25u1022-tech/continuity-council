FROM node:18-alpine AS frontend-build

WORKDIR /app/frontend
COPY frontend/package.json frontend/yarn.lock ./
RUN corepack enable && yarn install --frozen-lockfile

COPY frontend/ ./
ENV REACT_APP_BACKEND_URL=
RUN yarn build

FROM nikolaik/python-nodejs:python3.11-nodejs18-slim

WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY clickhouse/ ./clickhouse/
COPY scripts/ ./scripts/
COPY --from=frontend-build /app/frontend/build ./frontend/build

ENV FRONTEND_BUILD_DIR=../frontend/build
EXPOSE 8000

WORKDIR /app/backend
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]