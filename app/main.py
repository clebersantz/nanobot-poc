import os
import json
import math
import tempfile
from typing import List

import pytesseract
from pdf2image import convert_from_path
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from openai import OpenAI
from pydantic import BaseModel

from app import odoo_crm

MAX_PAGES_PER_PDF = int(os.getenv("MAX_PAGES_PER_PDF", "5"))
TOP_K_PAGES = int(os.getenv("TOP_K_PAGES", "3"))

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
# Odoo CRM endpoints — powered by the AI agent + knowledge base
# ---------------------------------------------------------------------------

# Maximum number of LLM ↔ tool-call turns in the agent loop
_CRM_MAX_TURNS = int(os.getenv("CRM_AGENT_MAX_TURNS", "10"))

# Load the Odoo CRM knowledge file once at startup
_CRM_KNOWLEDGE = odoo_crm.load_knowledge()

# System prompt: identity + full knowledge base
_CRM_SYSTEM_PROMPT = (
    "You are Nanobot, an intelligent CRM assistant integrated with Odoo.\n\n"
    "Use the knowledge below to understand the Odoo CRM data model and API, "
    "then use the available tools (`odoo_search`, `odoo_read`, `odoo_write`, `odoo_call`) "
    "to complete the requested task.\n\n"
    "## Odoo CRM Knowledge\n\n"
    + _CRM_KNOWLEDGE
)

# Generic low-level Odoo XML-RPC tools exposed to the AI agent
_CRM_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "odoo_search",
            "description": (
                "Search Odoo records matching a domain filter and return a list of IDs. "
                "Use this to find stage IDs (model='crm.stage') or lead IDs (model='crm.lead')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Odoo model name, e.g. 'crm.lead' or 'crm.stage'."},
                    "domain": {
                        "type": "array",
                        "description": "Odoo domain filter list, e.g. [[\"name\",\"ilike\",\"INITIAL\"]].",
                        "items": {},
                    },
                    "limit": {"type": "integer", "description": "Max records to return (default 100)."},
                    "offset": {"type": "integer", "description": "Records to skip (default 0)."},
                },
                "required": ["model", "domain"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "odoo_read",
            "description": "Read specific fields from a list of Odoo record IDs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Odoo model name."},
                    "ids": {"type": "array", "items": {"type": "integer"}, "description": "List of record IDs."},
                    "fields": {"type": "array", "items": {"type": "string"}, "description": "Field names to return."},
                },
                "required": ["model", "ids", "fields"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "odoo_write",
            "description": "Update fields on a list of Odoo records.",
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Odoo model name."},
                    "ids": {"type": "array", "items": {"type": "integer"}, "description": "Record IDs to update."},
                    "values": {"type": "object", "description": "Dict of field → value to write, e.g. {\"stage_id\": 7}."},
                },
                "required": ["model", "ids", "values"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "odoo_call",
            "description": (
                "Call any Odoo model method, e.g. 'message_post' to add a chatter note. "
                "args[0] is usually a list of record IDs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "model": {"type": "string", "description": "Odoo model name."},
                    "method": {"type": "string", "description": "Method name to invoke."},
                    "args": {"type": "array", "description": "Positional arguments. First element is typically a list of IDs.", "items": {}},
                    "kwargs": {"type": "object", "description": "Keyword arguments dict."},
                },
                "required": ["model", "method", "args", "kwargs"],
            },
        },
    },
]

# Map tool names to odoo_crm callables
_TOOL_DISPATCH = {
    "odoo_search": lambda a: odoo_crm.tool_odoo_search(**a),
    "odoo_read":   lambda a: odoo_crm.tool_odoo_read(**a),
    "odoo_write":  lambda a: odoo_crm.tool_odoo_write(**a),
    "odoo_call":   lambda a: odoo_crm.tool_odoo_call(**a),
}


def _run_crm_agent(task: str) -> dict:
    """Run the Nanobot CRM AI agent for the given *task* description.

    Returns a dict with ``actions`` (list of tool calls + results) and
    ``summary`` (final natural-language response from the agent).
    """
    messages: list = [
        {"role": "system", "content": _CRM_SYSTEM_PROMPT},
        {"role": "user", "content": task},
    ]
    actions_taken: list[dict] = []
    final_summary = ""

    for _ in range(_CRM_MAX_TURNS):
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.1,
            messages=messages,
            tools=_CRM_TOOLS,
            tool_choice="auto",
        )
        msg = response.choices[0].message
        messages.append(msg.model_dump(exclude_unset=True))

        if not msg.tool_calls:
            final_summary = msg.content or ""
            break

        for tc in msg.tool_calls:
            tool_name = tc.function.name
            args: dict = {}
            try:
                args = json.loads(tc.function.arguments)
                tool_result = _TOOL_DISPATCH[tool_name](args)
            except json.JSONDecodeError as exc:
                tool_result = {"error": f"Invalid JSON arguments for {tool_name}: {tc.function.arguments!r} — {exc}"}
            except KeyError:
                tool_result = {"error": f"Unknown tool: {tool_name}"}
            except Exception as exc:
                tool_result = {"error": str(exc)}

            actions_taken.append({"tool": tool_name, "args": args, "result": tool_result})
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(tool_result),
            })

    if not final_summary:
        final_summary = f"Agent reached the maximum number of turns ({_CRM_MAX_TURNS}) without finishing."

    return {"actions": actions_taken, "summary": final_summary}


class CRMWebhookPayload(BaseModel):
    lead_id: int


@app.post("/v1/crm/webhook", summary="Webhook: Nanobot processa lead do Odoo CRM usando IA")
async def crm_webhook(payload: CRMWebhookPayload):
    """Receive a Lead ID via webhook.

    Nanobot reads its knowledge base and uses generic Odoo tools to inspect
    the lead, post the processing message, and advance it to IN PROGRESS.
    """
    try:
        result = _run_crm_agent(f"Process CRM lead ID {payload.lead_id}.")
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro no agente Nanobot: {exc}")

    return JSONResponse({"lead_id": payload.lead_id, **result})


@app.post("/v1/crm/process-initial-leads", summary="Nanobot processa todos os leads em estágio INITIAL no Odoo CRM")
async def process_initial_leads():
    """Nanobot reads its knowledge base and processes every lead in the INITIAL stage."""
    try:
        result = _run_crm_agent(
            "Find all CRM leads currently in the INITIAL stage and process each one: "
            "post 'Hello, processed by Nanobot' and move them to the IN PROGRESS stage."
        )
    except EnvironmentError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erro no agente Nanobot: {exc}")

    return JSONResponse(result)
