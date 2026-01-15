# PLANZ

PLANZ is a prototype-first, cloud-ready service for collecting real-world events, storing them in a database, and selectively syncing them to Google Calendar.

## Structure
- `app/` core application package
  - `api/` HTTP endpoints
  - `config.py` settings via Pydantic
  - `db/` SQLAlchemy models and Alembic scaffolding
  - `domain/` schemas and constants
  - `services/` integrations (calendar, fetch, extract, etc.)
  - `pipelines/` orchestration entrypoints
  - `scripts/` CLI helpers
  - `tests/` test placeholders

## Run locally
Create a virtual environment, install dependencies, and start the API:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:create_app --factory --reload
```

## Weekly pipeline (placeholder)
The weekly pipeline will be invoked via:

```bash
python app/scripts/run_weekly.py
```
