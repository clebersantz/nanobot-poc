# Copilot Instructions for Nanobot POC

## Project Overview

Nanobot POC is a lightweight FastAPI application that enables **chat with PDF documents** using OCR and OpenAI. It extracts text from scanned PDFs via Tesseract OCR, retrieves the most relevant pages using OpenAI embeddings (cosine similarity), and answers user questions through the OpenAI chat API.

There is no database or persistent storage — all processing is done in-memory per request.

## Tech Stack

- **Language:** Python 3.11
- **Framework:** FastAPI with Uvicorn
- **OCR:** Tesseract (`pytesseract`) + Poppler (`pdf2image`) — Portuguese and English language packs
- **LLM:** OpenAI `gpt-4o-mini` for chat completions
- **Embeddings:** OpenAI `text-embedding-3-small` for semantic retrieval
- **Deployment:** Docker / Docker Compose (single container, port 8000)

## Repository Structure

```
app/
  main.py          # All application logic: routes, helpers, HTML UI
Dockerfile         # Python 3.11-slim + Tesseract + Poppler
docker-compose.yml # Single service, reads .env for OPENAI_API_KEY
requirements.txt   # Python dependencies
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /` | HTML chat UI with multi-PDF upload |
| `POST /v1/chat` | Accepts `message` (form) + `files[]` (PDFs), returns `answer` and `used_sources` |
| `POST /v1/ocr` | Returns raw OCR text per page for debugging |
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

- All application code lives in `app/main.py`. Keep logic consolidated there unless the file grows significantly.
- Helper functions (`_ocr_pdf`, `_embed`, `_cosine_similarity`, `_retrieve_top_k`, `_validate_pdf_upload`) are pure/stateless and should remain independently testable.
- Use `tempfile.TemporaryDirectory` for any file I/O — never write to the project directory at runtime.
- Prefer `HTTPException` with meaningful status codes and Portuguese error messages (consistent with existing messages).
- The OpenAI client is instantiated at module level and reads `OPENAI_API_KEY` from the environment automatically.
- When changing OCR or embedding behaviour, keep `MAX_PAGES_PER_PDF` and `TOP_K_PAGES` configurable via environment variables.
- System prompts should instruct the model to answer only from provided document context.

## Testing

There is currently no automated test suite. When adding tests, place them in a `tests/` directory and use `pytest`. Mock the OpenAI client and `pytesseract`/`pdf2image` calls to avoid external dependencies in CI.
