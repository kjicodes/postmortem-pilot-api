# The Post-Mortem Pilot

An internal engineering tool that turns incident reports into organizational memory. Post-mortems usually get written once and never read again, so teams end up repeating the same incidents because their history isn't searchable. This app fixes that: an engineer hitting an error can paste a stack trace or upload a file to surface similar past incidents for context during triage, and after resolving it, they document what happened and what fixed it while the LLM acts as an editor, rewording and structuring it into a clean post-mortem. Over time, the knowledge base surfaces recurring patterns across incidents, giving teams the visibility to have informed conversations about root causes and longer-term fixes.

## Tech Stack

- **Backend:** Python, Django, Django REST Framework
- **Database:** PostgreSQL + pgvector
- **AI/LLM:** OpenAI via LangChain
- **Pattern Detection:** scikit-learn
- **Async Processing:** Celery + Redis
- **Cloud:** AWS S3, Docker
- **Testing:** pytest, Postman

## Features

- Paste a stack trace, error log, or upload a document to surface similar past incidents 
- After resolving an incident, document what happened, what you tried, and what fixed it. The LLM acts as an editor, restructuring your report into a clean, consistent post-mortem
- Upload existing post-mortem documents (PDF or DOCX) to seed the knowledge base with historical incident data
- Cross-incident pattern detection using KMeans clustering and LLM summarization, surfacing recurring root causes and services that fail repeatedly so teams can catch systemic issues early

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
# Terminal 1: Django server
python manage.py runserver

# Terminal 2: Celery worker
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

## API Endpoints

### Incidents

| Method      | Endpoint | Description                                                                                                                              |
|-------------|----------|------------------------------------------------------------------------------------------------------------------------------------------|
| `POST`      | `/api/incidents/` | Submit a complete report of a resolved incident. The LLM rewords and structures it into a polished post-mortem, saves it, and returns it |
| `POST`      | `/api/incidents/search/` | Submit raw text or a document file, then runs vector similarity search and returns matching past incidents.                              |
| `GET`       | `/api/incidents/` | List all incident reports                                                                                                                |
| `GET`       | `/api/incidents/<uuid>/` | Retrieve a specific incident report                                                                                                      |
| `PUT/PATCH` | `/api/incidents/<uuid>/` | Edit a generated report                                                                                                                  |
| `DELETE`    | `/api/incidents/<uuid>/` | Remove an incident                                                                                                                       |
| `GET`       | `/api/incidents/<uuid>/similar/` | Find similar incidents                                                                                                                   |

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

## Example

**Submit a new incident**
```json
POST /api/incidents/
{
  "raw_input": "Traceback (most recent call last):\n  File \"app.py\"...",
  "title": "Checkout service returning 500s",
  "description": "Payment service threw on every checkout request after a bad deploy.",
  "severity": "HIGH",
  "affected_systems": ["checkout-service", "payment-service"],
  "timeline": "Deploy went out at 2:14pm; error rate spiked immediately.",
  "root_cause": "A bad deploy removed a required environment variable.",
  "resolution": "Rolled back the deploy at 2:18pm; service restored by 2:40pm.",
  "prevention": "Add pre-deploy config validation to CI."
}
```
All fields are required except `notes`. Returns the incident with `status: PENDING`. Poll `GET /api/incidents/<uuid>/` until `status` is `COMPLETED`, once the LLM finishes rewording and structuring what you submitted.

## Async Processing

All LLM and embedding operations run asynchronously via Celery to avoid HTTP request timeouts. The workflow for incident processing is:

```
POST /incidents → Save with PENDING status → Return 202 ACCEPTED
                                           → Celery task: LLM edits/rewords the submitted report + generates embedding
                                                         → Update record → COMPLETED or FAILED
```

## Roadmap

- [x] Complete testing
- [ ] Build Next.js + TypeScript front-end
