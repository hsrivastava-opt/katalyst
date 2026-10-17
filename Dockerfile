# Full Google Cloud Run deploy: React production build + FastAPI + Gemini/ADK adapters.
FROM node:22-alpine AS frontend-build
WORKDIR /workspace/frontend
COPY frontend/package.json frontend/package-lock.json frontend/tsconfig.json frontend/vite.config.ts frontend/index.html ./
COPY frontend/src ./src
COPY frontend/public ./public
RUN npm ci --no-audit --no-fund && npm run build

FROM python:3.12-slim
WORKDIR /workspace
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8080
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/app ./backend/app
COPY frontend/offline ./frontend/offline
COPY --from=frontend-build /workspace/frontend/dist ./frontend/dist
RUN mkdir -p /workspace/data
WORKDIR /workspace/backend
CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
