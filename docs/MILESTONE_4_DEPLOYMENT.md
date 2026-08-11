# BizPilot AI Milestone 4 Cloud Run Deployment

## 1. Google Cloud Project Creation

```bash
gcloud config set project YOUR_PROJECT_ID
```

## 2. Required APIs And Services

```bash
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com sqladmin.googleapis.com
```

## 3. Authentication

```bash
gcloud auth login
gcloud auth application-default login
```

## 4. Docker And Build Process

```bash
gcloud artifacts repositories create YOUR_REPOSITORY --repository-format=docker --location=REGION
gcloud builds submit --tag REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REPOSITORY/bizpilot-ai
```

## 5. Cloud Run Deployment

`asia-south1` is a practical default region for a Madurai-focused demo.

```bash
gcloud run deploy bizpilot-ai \
  --image REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REPOSITORY/bizpilot-ai \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars FLASK_DEBUG=false,PORT=8080
```

## 6. Environment Variables

```text
SECRET_KEY
DATABASE_URL
GEMINI_API_KEY
GROQ_API_KEY
PRIMARY_AI_PROVIDER
FALLBACK_AI_PROVIDER
ENABLE_RULE_BASED_FALLBACK
AI_REQUEST_TIMEOUT
AI_MAX_RETRIES
WEATHER_LATITUDE
WEATHER_LONGITUDE
WEATHER_LOCATION
SHORT_TERM_MEMORY_LIMIT
LONG_TERM_MEMORY_LIMIT
PORT
```

Use Secret Manager for sensitive values. Never commit `.env`.

## 7. PostgreSQL Configuration

Use managed PostgreSQL such as Cloud SQL for PostgreSQL. The app reads the connection from `DATABASE_URL`.

```text
postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
```

Do not use container-local SQLite for production data.

## 8. Database Migration

```bash
flask --app app db upgrade
```

Run this from a trusted environment with the same `DATABASE_URL`, or use a one-off Cloud Run job.

## 9. Health Check

```bash
curl https://YOUR_CLOUD_RUN_URL/api/health
```

Expected status is `ok` with `database: ok`.

## 10. Testing Deployed Application

Run these demo prompts after login:

```text
Which products should I restock?
Which product should I promote?
Why did you choose that?
How is my business performing this month?
What offer should I provide based on Madurai weather?
Calculate profit margin for revenue 50000 and expenses 32000.
```

## 11. Logs

```bash
gcloud run services logs read bizpilot-ai --region asia-south1
```

Logs should be useful but safe: workflow ID, agent name, tool name, status, duration, and safe error category.

## 12. Updating And Redeploying

```bash
gcloud builds submit --tag REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REPOSITORY/bizpilot-ai
gcloud run deploy bizpilot-ai --image REGION-docker.pkg.dev/YOUR_PROJECT_ID/YOUR_REPOSITORY/bizpilot-ai --region asia-south1
```

## 13. Troubleshooting

Check `/api/health`, Cloud Run logs, database connectivity, Secret Manager permissions, and whether `DATABASE_URL` uses the correct driver prefix.

## 14. Security Considerations

Use a strong `SECRET_KEY`, least-privilege service accounts, HTTPS-only Cloud Run traffic, private database access where possible, and Secret Manager for credentials.

## 15. Estimated Architecture

```mermaid
flowchart LR
    GH[GitHub] --> CB[Cloud Build]
    CB --> AR[Artifact Registry]
    AR --> CR[Cloud Run]
    CR --> PG[(Managed PostgreSQL)]
    CR --> AI[Gemini and Groq]
```
