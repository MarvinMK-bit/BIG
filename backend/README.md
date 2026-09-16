# Backend

FastAPI backend.

## Local development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # then edit DATABASE_URL etc.

uvicorn app.main:app --reload
```

The API is served at `http://localhost:8000`, with a health check at `/health`.

## Migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```
