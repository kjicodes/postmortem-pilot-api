# The Post-Mortem Pilot

An internal engineering tool that turns incident reports into organizational memory. Engineers paste a stack trace or error log and the app generates a structured post-mortem report, searches past incidents for similar patterns using vector similarity, and surfaces cross-incident trends over time.

## The Problem

Post-mortems get written and never read again. Teams repeat the same incidents because their history isn't searchable or analyzed. This app turns individual incidents into a knowledge base that gets more valuable over time.

## Tech Stack

- **Backend:** Python, Django, Django REST Framework
- **Database:** PostgreSQL + pgvector
- **LLM / Embeddings:** OpenAI via LangChain
- **Async Processing:** Celery + Redis
- **File Storage:** AWS S3

## Features

- Submit a stack trace or error log -> LLM generates a structured post-mortem report asynchronously
- Vector similarity search surfaces past incidents with similar patterns
- Upload existing post-mortem documents (PDF or DOCX) to seed the knowledge base with historical data
- Cross-incident pattern detection using KMeans clustering and LLM summarization
- REST API backend designed to be embedded into existing systems for richer, context-aware reports

## Getting Started

### 1. Install system dependencies

```bash
brew install postgresql pgvector redis
brew services start postgresql
brew services start redis
```

### 2. Create the database and enable pgvector

In pgAdmin or psql:

```sql
CREATE DATABASE postmortem_pilot;
\c postmortem_pilot
CREATE EXTENSION IF NOT EXISTS vector;
```

### 3. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```
SECRET_KEY=your-django-secret-key
DB_NAME=postmortem_pilot
DB_USER=postgres
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432
OPENAI_API_KEY=your-openai-api-key
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_BUCKET_NAME=your-s3-bucket-name
AWS_REGION=us-east-1
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### 5. Run migrations

```bash
python manage.py migrate
```

### 6. Start the application

Redis runs as a background service via Homebrew (started in step 1). You need two terminal windows for the remaining processes:

```bash
# Terminal 1 — Django server
python manage.py runserver

# Terminal 2 — Celery worker
celery -A config worker --loglevel=info
```

## API Endpoints

### Incidents

| Method   | Endpoint | Description |
|----------|----------|-------------|
| `POST`   | `/api/incidents/` | Submit a stack trace or error log — LLM generates a structured report asynchronously |
| `GET`    | `/api/incidents/` | List all incident reports |
| `GET`    | `/api/incidents/<uuid>/` | Retrieve a specific incident report |
| `PATCH`  | `/api/incidents/<uuid>/` | Edit a generated report |
| `DELETE` | `/api/incidents/<uuid>/` | Remove an incident |
| `GET`    | `/api/incidents/<uuid>/similar/` | Find past incidents with similar patterns via vector similarity search |

#### POST /api/incidents/ — Request Body

```json
{
  "raw_input": "Traceback (most recent call last):\n  File \"app.py\"..."
}
```

#### Response

Returns the created incident immediately with `status: PENDING`. The LLM processes the report asynchronously. Poll `GET /api/incidents/<uuid>/` until `status` is `COMPLETED`.

---

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/` | Upload an existing post-mortem PDF or DOCX to seed the knowledge base |
| `GET` | `/api/documents/` | List uploaded documents |
| `DELETE` | `/api/documents/<uuid>/` | Remove a document |

#### POST /api/documents/ — Request

Send as `multipart/form-data` with a `file` field containing the PDF or DOCX.

#### Response

Returns the created document with `status: PENDING`. Text extraction and embedding generation happen asynchronously. Poll `GET /api/documents/<uuid>/` until `status` is `COMPLETED`.

---

### Patterns

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/patterns/` | Surface cross-incident trends using KMeans clustering and LLM summarization |

#### How it works

1. All incident embeddings are pulled from PostgreSQL
2. KMeans (scikit-learn) clusters them by semantic similarity — N scales dynamically with incident count (3 / 5 / 10 for small / medium / large datasets)
3. Each cluster is summarized by the LLM via LangChain
4. Cluster summaries are synthesized into a final pattern report
5. Results are cached in the database — recomputed when stale (default threshold: 1 hour)

---

## Async Processing

All LLM and embedding operations run asynchronously via Celery to avoid HTTP request timeouts. The workflow for incident processing is:

```
POST /incidents → Save with PENDING status → Return 202 ACCEPTED
                                           → Celery task: LLM report generation + embedding
                                                         → Update record → COMPLETED or FAILED
```

The same pattern applies to document processing.

---

## Roadmap

- [ ] **Cross-table vector similarity search** — extend `GET /incidents/<uuid>/similar/` to query both the `Incident` and `Document` tables, returning similar results from both. Currently only incidents are searched; documents have embeddings stored but are not yet included in similarity queries.
- [ ] **Frontend** — React + TypeScript interface with a home page presenting the app as a product, and an incident submission form
