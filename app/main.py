import json
import os
import math
import tempfile
import xmlrpc.client
from pathlib import Path
from typing import Any, List

import pytesseract
from pdf2image import convert_from_path
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from openai import OpenAI
from pydantic import BaseModel

MAX_PAGES_PER_PDF = int(os.getenv("MAX_PAGES_PER_PDF", "5"))
TOP_K_PAGES = int(os.getenv("TOP_K_PAGES", "3"))

# ---------------------------------------------------------------------------
# Odoo configuration (read from environment)
# ---------------------------------------------------------------------------
ODOO_URL = os.getenv("ODOO_URL", "")
ODOO_DB = os.getenv("ODOO_DB", "")
ODOO_USER = os.getenv("ODOO_USER", "")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "")

_KNOWLEDGE_FILE = Path(__file__).parent / "knowledge" / "odoo_crm.md"

app = FastAPI(title="Nanobot POC", description="Chat + OCR de PDFs via OpenAI")

client = OpenAI()  # reads OPENAI_API_KEY from env automatically


# ---------------------------------------------------------------------------
# HTML UI
# ---------------------------------------------------------------------------

HTML_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Nanobot POC – Chat com PDFs</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 800px; margin: 40px auto; padding: 0 16px; }
    h1 { color: #333; }
    textarea { width: 100%; height: 80px; margin-top: 8px; }
    input[type=file] { margin-top: 8px; display: block; }
    button { margin-top: 12px; padding: 8px 24px; background: #0070f3; color: #fff;
             border: none; border-radius: 4px; cursor: pointer; font-size: 1rem; }
    button:disabled { background: #999; cursor: not-allowed; }
    #status { margin-top: 12px; color: #555; }
    #error  { margin-top: 12px; color: #c00; white-space: pre-wrap; }
    #answer { margin-top: 16px; padding: 12px; background: #f6f8fa; border-radius: 4px;
              white-space: pre-wrap; }
    #sources { margin-top: 8px; font-size: 0.85rem; color: #666; }
  </style>
</head>
<body>
  <h1>🤖 Nanobot POC</h1>
  <form id="chatForm">
    <label><strong>Mensagem:</strong></label>
    <textarea id="message" name="message" placeholder="Digite sua pergunta…" required></textarea>

    <label><strong>PDFs (opcional, múltiplos):</strong></label>
    <input type="file" id="files" name="files" accept=".pdf" multiple/>

    <button type="submit" id="sendBtn">Enviar</button>
  </form>

  <div id="status"></div>
  <div id="error"></div>
  <div id="answer"></div>
  <div id="sources"></div>

  <script>
    document.getElementById('chatForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn    = document.getElementById('sendBtn');
      const status = document.getElementById('status');
      const errDiv = document.getElementById('error');
      const ansDiv = document.getElementById('answer');
      const srcDiv = document.getElementById('sources');

      btn.disabled = true;
      status.textContent = 'Processando…';
      errDiv.textContent = '';
      ansDiv.textContent = '';
      srcDiv.textContent = '';

      try {
        const fd = new FormData();
        fd.append('message', document.getElementById('message').value);
        const filesInput = document.getElementById('files');
        for (const f of filesInput.files) { fd.append('files', f); }

        const resp = await fetch('/v1/chat', { method: 'POST', body: fd });
        const data = await resp.json();

        if (!resp.ok) {
          errDiv.textContent = 'Erro ' + resp.status + ': ' + (data.detail || JSON.stringify(data));
        } else {
          ansDiv.textContent = data.answer;
          if (data.used_sources && data.used_sources.length) {
            srcDiv.textContent = 'Fontes: ' + data.used_sources.join(', ');
          }
        }
      } catch (err) {
        errDiv.textContent = 'Erro de rede: ' + err.message;
      } finally {
        btn.disabled = false;
        status.textContent = '';
      }
    });
  </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, summary="UI de chat")
async def root():
    return HTMLResponse(content=HTML_PAGE)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ocr_pdf(path: str, max_pages: int) -> List[dict]:
    """Return list of {page, text} dicts for up to *max_pages* pages of the PDF."""
    images = convert_from_path(path, last_page=max_pages)
    results = []
    for i, img in enumerate(images, start=1):
        text = pytesseract.image_to_string(img, lang="por+eng")
        results.append({"page": i, "text": text.strip()})
    return results


def _embed(texts: List[str]) -> List[List[float]]:
    """Get embeddings for a list of texts using text-embedding-3-small."""
    response = client.embeddings.create(model="text-embedding-3-small", input=texts)
    return [item.embedding for item in response.data]


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _validate_pdf_upload(upload: UploadFile) -> None:
    """Raise HTTPException if the upload is not a valid PDF."""
    if not upload.filename:
        raise HTTPException(status_code=400, detail="Arquivo sem nome fornecido.")
    if not upload.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail=f"Arquivo '{upload.filename}' não é PDF.")


def _retrieve_top_k(query: str, pages: List[dict], k: int) -> List[dict]:
    """Return top-k pages most similar to *query* using cosine similarity."""
    # Only consider pages that have actual text content
    pages = [p for p in pages if p.get("text", "").strip()]
    if not pages:
        return []
    texts = [p["text"] for p in pages]
    all_texts = [query] + texts
    embeddings = _embed(all_texts)
    query_emb = embeddings[0]
    page_embs = embeddings[1:]
    scored = [
        (page, _cosine_similarity(query_emb, emb))
        for page, emb in zip(pages, page_embs)
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:k]]


# ---------------------------------------------------------------------------
# POST /v1/chat
# ---------------------------------------------------------------------------

@app.post("/v1/chat", summary="Chat com PDFs via OCR + OpenAI")
async def chat(
    message: str = Form(...),
    files: List[UploadFile] = File(default=[]),
):
    all_pages: List[dict] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for upload in files:
            _validate_pdf_upload(upload)
            dest = os.path.join(tmpdir, upload.filename)  # type: ignore[arg-type]
            content = await upload.read()
            with open(dest, "wb") as f:
                f.write(content)
            try:
                pages = _ocr_pdf(dest, MAX_PAGES_PER_PDF)
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"Erro ao processar '{upload.filename}': {exc}")
            for p in pages:
                p["source"] = f"{upload.filename} p.{p['page']}"
            all_pages.extend(pages)

    if all_pages:
        top_pages = _retrieve_top_k(message, all_pages, TOP_K_PAGES)
    else:
        top_pages = []

    context_parts = [f"[{p['source']}]\n{p['text']}" for p in top_pages] if top_pages else []
    context_text = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "Você é um assistente especializado em análise de documentos. "
        "Responda APENAS com base nas fontes fornecidas. "
        "Se a resposta não estiver nas fontes, diga que não encontrou a informação. "
        "Seja preciso e conciso."
    )

    user_content = message
    if context_text:
        user_content = f"Contexto extraído dos documentos:\n\n{context_text}\n\nPergunta: {message}"

    try:
        completion = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.2,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro na API OpenAI: {exc}")

    answer = completion.choices[0].message.content or ""
    used_sources = [p["source"] for p in top_pages]

    return JSONResponse({"answer": answer, "used_sources": used_sources})


# ---------------------------------------------------------------------------
# POST /v1/ocr  (debug)
# ---------------------------------------------------------------------------

@app.post("/v1/ocr", summary="OCR de PDFs (debug)")
async def ocr(
    files: List[UploadFile] = File(...),
):
    result = {}
    with tempfile.TemporaryDirectory() as tmpdir:
        for upload in files:
            _validate_pdf_upload(upload)
            dest = os.path.join(tmpdir, upload.filename)  # type: ignore[arg-type]
            content = await upload.read()
            with open(dest, "wb") as f:
                f.write(content)
            try:
                pages = _ocr_pdf(dest, MAX_PAGES_PER_PDF)
            except Exception as exc:
                raise HTTPException(status_code=422, detail=f"Erro ao processar '{upload.filename}': {exc}")
            result[upload.filename] = pages
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# Odoo XML-RPC helpers
# ---------------------------------------------------------------------------

def _odoo_uid() -> int:
    """Authenticate against Odoo and return the user ID (uid)."""
    if not all([ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD]):
        raise HTTPException(
            status_code=503,
            detail="Odoo not configured. Set ODOO_URL, ODOO_DB, ODOO_USER, ODOO_PASSWORD.",
        )
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_PASSWORD, {})
    if not uid:
        raise HTTPException(status_code=401, detail="Odoo authentication failed.")
    return int(uid)


def _odoo_models():
    """Return an authenticated XML-RPC proxy for the Odoo object endpoint."""
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")


def _odoo_search_read(model: str, domain: list, fields: list) -> list:
    uid = _odoo_uid()
    models = _odoo_models()
    return models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        model, "search_read",
        [domain],
        {"fields": fields},
    )


def _odoo_write(model: str, ids: list, values: dict) -> bool:
    uid = _odoo_uid()
    models = _odoo_models()
    return models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        model, "write",
        [ids, values],
    )


def _odoo_message_post(model: str, record_id: int, body: str) -> int:
    uid = _odoo_uid()
    models = _odoo_models()
    return models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        model, "message_post",
        [[record_id]],
        {"body": body},
    )


# ---------------------------------------------------------------------------
# OpenAI tool definitions for Odoo
# ---------------------------------------------------------------------------

_ODOO_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "odoo_search_read",
            "description": (
                "Search and read records from an Odoo model using domain filters."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Odoo model technical name, e.g. 'crm.lead' or 'crm.stage'.",
                    },
                    "domain": {
                        "type": "array",
                        "description": "Odoo domain filter list, e.g. [[\"id\",\"=\",42]].",
                        "items": {},
                    },
                    "fields": {
                        "type": "array",
                        "description": "List of field names to return.",
                        "items": {"type": "string"},
                    },
                },
                "required": ["model", "domain", "fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "odoo_write",
            "description": "Update field values on one or more existing Odoo records.",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Odoo model technical name, e.g. 'crm.lead'.",
                    },
                    "ids": {
                        "type": "array",
                        "description": "List of record IDs to update.",
                        "items": {"type": "integer"},
                    },
                    "values": {
                        "type": "object",
                        "description": "Dict of field names to new values.",
                    },
                },
                "required": ["model", "ids", "values"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "odoo_message_post",
            "description": "Post a message in the chatter of an Odoo record.",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {
                        "type": "string",
                        "description": "Odoo model technical name, e.g. 'crm.lead'.",
                    },
                    "record_id": {
                        "type": "integer",
                        "description": "ID of the record to post the message on.",
                    },
                    "body": {
                        "type": "string",
                        "description": "Message body (plain text or HTML).",
                    },
                },
                "required": ["model", "record_id", "body"],
            },
        },
    },
]


def _dispatch_tool(name: str, arguments: dict) -> Any:
    """Execute an Odoo tool call and return a JSON-serialisable result."""
    if name == "odoo_search_read":
        return _odoo_search_read(
            arguments["model"],
            arguments["domain"],
            arguments["fields"],
        )
    if name == "odoo_write":
        return _odoo_write(
            arguments["model"],
            arguments["ids"],
            arguments["values"],
        )
    if name == "odoo_message_post":
        return _odoo_message_post(
            arguments["model"],
            arguments["record_id"],
            arguments["body"],
        )
    raise ValueError(f"Unknown tool: {name}")


# ---------------------------------------------------------------------------
# POST /v1/webhook/odoo
# ---------------------------------------------------------------------------

class OdooWebhookPayload(BaseModel):
    lead_id: int


@app.post("/v1/webhook/odoo", summary="Webhook: process an Odoo CRM lead")
async def odoo_webhook(payload: OdooWebhookPayload):
    """Receive a lead ID and autonomously process it using the Odoo CRM knowledge."""
    try:
        knowledge = _KNOWLEDGE_FILE.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Odoo CRM knowledge file not found.")

    system_prompt = (
        "You are Nanobot, an autonomous CRM agent.\n\n"
        "## Knowledge\n\n"
        f"{knowledge}\n\n"
        "Use the provided tools to act on Odoo. "
        "After completing all steps, reply with a short summary of what you did."
    )
    user_message = f"Process lead ID: {payload.lead_id}"

    messages: list = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    # Agentic loop: let OpenAI call tools until it produces a final answer.
    max_iterations = 10
    for _ in range(max_iterations):
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                tools=_ODOO_TOOLS,
                tool_choice="auto",
                messages=messages,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"OpenAI API error: {exc}")

        choice = response.choices[0]
        messages.append(choice.message)

        if choice.finish_reason == "tool_calls" and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                    result = _dispatch_tool(tc.function.name, args)
                    tool_result = json.dumps(result)
                except HTTPException:
                    raise
                except Exception as exc:
                    tool_result = json.dumps({"error": str(exc)})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": tool_result,
                })
        else:
            # Model produced a final text answer — we're done.
            summary = choice.message.content or "Done."
            return JSONResponse({"lead_id": payload.lead_id, "summary": summary})

    raise HTTPException(status_code=500, detail="Agent did not converge after max iterations.")
