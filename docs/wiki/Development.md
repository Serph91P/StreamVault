# Development

## Backend

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Frontend

```bash
cd app/frontend
npm install
npm run dev
```

## Tests and checks

```bash
ruff format --check app tests
ruff check app tests
pytest tests/ -q
cd app/frontend
npm run lint:tokens
npm run type-check
npm run build
```

## Project layout

| Path | Purpose |
| --- | --- |
| `app/routes` | FastAPI route modules |
| `app/services` | Business logic and integration services |
| `app/frontend` | Vue PWA frontend |
| `migrations` | Database migrations |
| `docker` | Compose and container related files |
| `tests` | Python test suite |
