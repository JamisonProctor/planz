FROM python:3.11-slim AS base
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app/ ./app/
COPY pyproject.toml .

FROM base AS web
ENV ENV=production
ENV DATABASE_URL=sqlite:////app/data/planz.db
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker
RUN pip install --no-cache-dir playwright && playwright install chromium && playwright install-deps chromium
ENV ENV=production
ENV DATABASE_URL=sqlite:////app/data/planz.db
CMD ["python", "-m", "app.scripts.extract_muenchen_kinder", "--persist"]
