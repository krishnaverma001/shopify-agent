# AI Shopping Agent

Enterprise-grade FastAPI backend for an AI-native Shopify shopping assistant.

## Architecture

- FastAPI API Gateway
- Redis caching and queueing
- PostgreSQL persistence
- Vector search + SQL hybrid retrieval
- Deterministic tool execution and ranking
- Shopify webhook ingestion and inventory validation

## Getting Started

1. Copy `.env.example` to `.env` and fill values.
2. Install dependencies:

```bash
python -m pip install -r requirements.txt
```

3. Run the app:

```bash
uvicorn app.main:app --reload
```

## Endpoints

- `GET /api/v1/health`
- `POST /api/v1/agent/query`
- `POST /api/v1/webhooks/shopify/product_update`

## Project Structure

- `app/main.py` - entrypoint and router registration
- `app/config.py` - application settings and environment
- `app/api/v1` - API router implementations
- `app/services` - agent orchestration, retrieval, ranking, and Shopify integration
- `app/db` - database models and repository layer
- `app/schemas` - request/response contracts
- `app/tasks` - async worker tasks and webhook processing
- `app/utils` - guardrails, caching keys, and helper functions


DELETE FROM supabase_migrations.schema_migrations;

DROP TABLE IF EXISTS review_embeddings CASCADE;
DROP TABLE IF EXISTS product_embeddings CASCADE;
DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS product_variants CASCADE;
DROP TABLE IF EXISTS products CASCADE;

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO service_role;

adaptive search that keeps asking constraints OR expanding results until confidence is high