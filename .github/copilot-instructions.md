# Copilot Instructions for Nanobot POC

## Project Overview

Nanobot POC is a nanobot.ai  AI Agent / RAG that helps ODOO CRM Leads Tasks

## Tech Stack

- **Language:** Python 3.11
- **Framework:** FastAPI 
- **OCR:** Tesseract (`pytesseract`) + Poppler (`pdf2image`) — Portuguese and English language packs
- **LLM:** OpenAI `gpt-4o-mini` for chat completions
- **Embeddings:** OpenAI `text-embedding-3-small` for semantic retrieval
- **Deployment:** Docker / Docker Compose (single container, port 8000)
- **ODOO Version** ODOO 18 OCA/Communitie
- **XML-RPC**

## Repository Structure

```
app/
  main.py          # All application logic: routes, helpers, HTML UI
docs/              # All AI knowledge base documents
Dockerfile         # Python 3.11-slim + Tesseract + Poppler
docker-compose.yml # Single service, reads .env for OPENAI_API_KEY
requirements.txt   # Python dependencies
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | HTML chat UI with multi-PDF upload |
| `POST /v1/nanobot-poc/odoo/webhook/crm/lead` | Accepts JSON ODOO CRM Lead data, such as lead_id |
| `GET /docs` | Auto-generated Swagger UI |

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key — never commit this |
| `MAX_PAGES_PER_PDF` | `5` | Maximum pages to OCR per PDF |
| `TOP_K_PAGES` | `3` | Top-K most relevant pages sent to the LLM |

The `.env` file is git-ignored and must never be committed.

## Running Locally

```bash
# Build and start the container
docker compose up --build

# App available at:
# http://localhost:8000/       (chat UI)
# http://localhost:8000/docs   (Swagger)
```

## Development Guidelines

  TODO 

## Testing

  TODO
