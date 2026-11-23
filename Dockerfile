# Build the React frontend, then serve it and the API from one FastAPI process.
FROM node:22-slim AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
# Tesseract does the local OCR for receipt scanning.
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ ./
COPY --from=frontend /frontend/dist /app/frontend/dist
RUN useradd --create-home --uid 1000 app && mkdir -p data && chown app data
USER app
ENV DATA_DIR=/app/backend/data REFRESH_AT=05:00
EXPOSE 8420
# In demo mode, build the demo data before serving; otherwise refresh once.
CMD ["sh", "-c", "if [ \"$DEMO_MODE\" = \"true\" ]; then python -m scripts.seed_demo; else python -m scripts.refresh_data || true; fi; exec uvicorn app.main:app --host 0.0.0.0 --port 8420"]
