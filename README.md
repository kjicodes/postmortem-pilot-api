# The Post-Mortem Pilot

An internal engineering tool that turns incident reports into organizational memory. When an engineer hits an error, they can paste a stack trace or error log to surface similar past incidents, giving them useful context and a starting point rather than debugging blind. After resolution, they submit the incident to get a structured post-mortem draft to build on, filling in what actually happened, what they tried, and what fixed it. Over time, the knowledge base surfaces recurring patterns across incidents, giving teams the visibility they need for informed conversations about root causes and longer-term fixes.

## The Problem

Post-mortems get written and never read again. Teams lose institutional knowledge after every incident because their history isn't searchable or connected. This app turns individual incidents into a living knowledge base that gets more valuable the more it's used.

## Tech Stack

- **Backend:** Python, Django, Django REST Framework
- **Database:** PostgreSQL + pgvector
- **LLM / Embeddings:** OpenAI via LangChain
- **Async Processing:** Celery + Redis
- **Cloud:** AWS S3 (document storage), IAM
- **Containerization:** Docker
- **Testing:** pytest, Postman

## Features

- Paste a stack trace, error log, or upload a document to surface similar past incidents and gain context during triage 
- Submit a resolved incident to generate a structured post-mortem draft via LLM, giving engineers a starting point to complete with what actually happened and how it was fixed
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

### Running with Docker

Ensure Docker Desktop is running, then:

```bash
docker-compose up --build
```

The app will be available at `http://localhost:8000`. On first run, apply migrations:

```bash
docker-compose exec web python manage.py migrate
```

---

## API Endpoints

### Incidents

| Method   | Endpoint | Description                                                                                                                   |
|----------|----------|-------------------------------------------------------------------------------------------------------------------------------|
| `POST`   | `/api/incidents/` | Submit a stack trace or error log, then LLM generates a structured report, saves it, and returns it                           |
| `POST`   | `/api/incidents/search/` | Submit raw text or a document file, then runs vector similarity search and returns matching past incidents. |
| `GET`    | `/api/incidents/` | List all incident reports                                                                                                     |
| `GET`    | `/api/incidents/<uuid>/` | Retrieve a specific incident report                                                                                           |
| `PATCH`  | `/api/incidents/<uuid>/` | Edit a generated report                                                                                                       |
| `DELETE` | `/api/incidents/<uuid>/` | Remove an incident                                                                                                            |
| `GET`    | `/api/incidents/<uuid>/similar/` | Find incidents similar to a specific documented one         |

### Documents

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/documents/` | Upload an existing post-mortem PDF or DOCX to seed the knowledge base |
| `GET` | `/api/documents/` | List uploaded documents |
| `DELETE` | `/api/documents/<uuid>/` | Remove a document |

### Patterns

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/patterns/` | Surface cross-incident trends using KMeans clustering and LLM summarization |

## Examples

**Submit a new incident**
```json
POST /api/incidents/
{
  "raw_input": "Traceback (most recent call last):\n  File \"app.py\"..."
}
```
Returns the incident with `status: PENDING`. Poll `GET /api/incidents/<uuid>/` until `status` is `COMPLETED`.

**Search for similar incidents**
```json
POST /api/incidents/search/
{
  "query": "Traceback (most recent call last):\n  File \"app.py\"..."
}
```
Returns a list of past incidents ranked by vector similarity.

## Async Processing

All LLM and embedding operations run asynchronously via Celery to avoid HTTP request timeouts. The workflow for incident processing is:

```
POST /incidents → Save with PENDING status → Return 202 ACCEPTED
                                           → Celery task: LLM report generation + embedding
                                                         → Update record → COMPLETED or FAILED
```

The same pattern applies to document processing.

## Roadmap

- [ ] Complete testing
- [ ] Work on frontend (using React)
