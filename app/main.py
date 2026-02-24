import os
import math
import pathlib
import tempfile
import xmlrpc.client
from typing import List

import pytesseract
from pdf2image import convert_from_path
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from openai import OpenAI
from pydantic import BaseModel

MAX_PAGES_PER_PDF = int(os.getenv("MAX_PAGES_PER_PDF", "5"))
TOP_K_PAGES = int(os.getenv("TOP_K_PAGES", "3"))

# ---------------------------------------------------------------------------
# ODOO Configuration
# ---------------------------------------------------------------------------

ODOO_URL = os.getenv("ODOO_URL", "")
ODOO_DB = os.getenv("ODOO_DB", "")
ODOO_USER = os.getenv("ODOO_USER", "")
ODOO_API_KEY = os.getenv("ODOO_API_KEY", "")
ODOO_STAGE_INITIAL = os.getenv("ODOO_STAGE_INITIAL", "INITIAL")
ODOO_STAGE_IN_PROCESS = os.getenv("ODOO_STAGE_IN_PROCESS", "IN PROCESS")

AGENT_MESSAGE = "Hello! This Lead has been processed by ODOO CRM Lead AI Agent"

# ---------------------------------------------------------------------------
# Knowledge Base (KB) RAG Configuration
# ---------------------------------------------------------------------------

KB_DIR = pathlib.Path(__file__).parent.parent / "docs" / "kb"
KB_CHUNK_SIZE_CHARS = int(os.getenv("KB_CHUNK_SIZE_CHARS", "1000"))
KB_TOP_K = int(os.getenv("KB_TOP_K", "5"))
KB_BUILD_COMMANDS = (
    "build knowledge base",
    "build kb",
    "construir base de conhecimento",
    "treinar base de conhecimento",
)
ODOO_CHECK_CONNECTION_COMMANDS = (
    "check connection with odoo",
    "check odoo connection",
    "test odoo connection",
    "connect to odoo",
    "conectar ao odoo",
    "conectar com odoo",
    "verificar conexão com odoo",
    "verificar conexao com odoo",
)

_kb_chunks: List[dict] = []
_kb_embeddings: List[List[float]] = []
_kb_loaded = False

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
# Knowledge Base (KB) helpers
# ---------------------------------------------------------------------------

def _load_kb_chunks() -> List[dict]:
    """Load and chunk all markdown files from the KB directory."""
    chunks: List[dict] = []
    if not KB_DIR.exists():
        return chunks
    for md_file in sorted(KB_DIR.rglob("*.md")):
        content = md_file.read_text(encoding="utf-8")
        rel_path = str(md_file.relative_to(KB_DIR.parent.parent))
        paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 <= KB_CHUNK_SIZE_CHARS:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    chunks.append({"source": rel_path, "text": current})
                current = para
        if current:
            chunks.append({"source": rel_path, "text": current})
    return chunks


def _build_kb_index(force: bool = False) -> dict:
    """Build KB chunks and embeddings explicitly when requested by user."""
    global _kb_chunks, _kb_embeddings, _kb_loaded
    if _kb_loaded and not force:
        return {"loaded": True, "chunks": len(_kb_chunks)}
    _kb_chunks = _load_kb_chunks()
    _kb_embeddings = _embed([c["text"] for c in _kb_chunks]) if _kb_chunks else []
    _kb_loaded = True
    return {"loaded": True, "chunks": len(_kb_chunks)}


def _get_kb_context(query: str) -> List[dict]:
    """Return top-K most relevant KB chunks for the query."""
    global _kb_chunks, _kb_embeddings, _kb_loaded
    if not _kb_loaded:
        return []
    if not _kb_chunks:
        return []
    query_emb = _embed([query])[0]
    scored = [
        (chunk, _cosine_similarity(query_emb, emb))
        for chunk, emb in zip(_kb_chunks, _kb_embeddings)
    ]
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:KB_TOP_K]]


# ---------------------------------------------------------------------------
# ODOO XML-RPC helpers
# ---------------------------------------------------------------------------

def _odoo_connect():
    """Authenticate to ODOO via XML-RPC and return (uid, models_proxy)."""
    if not all([ODOO_URL, ODOO_DB, ODOO_USER, ODOO_API_KEY]):
        raise HTTPException(status_code=503, detail="ODOO connection not configured.")
    try:
        common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
        uid = common.authenticate(ODOO_DB, ODOO_USER, ODOO_API_KEY, {})
        if not uid:
            raise HTTPException(status_code=503, detail="ODOO authentication failed.")
        models_proxy = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")
        return uid, models_proxy
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"ODOO connection error: {exc}")


# ---------------------------------------------------------------------------
# POST /v1/chat
# ---------------------------------------------------------------------------

@app.post("/v1/chat", summary="Chat com PDFs via OCR + OpenAI")
async def chat(
    message: str = Form(...),
    files: List[UploadFile] = File(default=[]),
):
    message_normalized = message.strip().lower()

    if any(cmd in message_normalized for cmd in KB_BUILD_COMMANDS):
        try:
            kb_status = _build_kb_index()
            answer = f"Knowledge base built successfully. Total chunks indexed: {kb_status['chunks']}."
        except Exception as exc:
            answer = f"Failed to build knowledge base: {exc}"
        return JSONResponse(
            {
                "answer": answer,
                "used_sources": [],
                "agent_action": "build_knowledge_base",
            }
        )

    if any(cmd in message_normalized for cmd in ODOO_CHECK_CONNECTION_COMMANDS):
        try:
            uid, _ = _odoo_connect()  # models proxy intentionally unused in chat status check
            answer = f"ODOO connection successful. Authenticated user id: {uid}."
            connected = True
        except HTTPException as exc:
            answer = f"ODOO connection failed: {exc.detail}"
            connected = False
        return JSONResponse(
            {
                "answer": answer,
                "used_sources": [],
                "agent_action": "check_odoo_connection",
                "odoo_connected": connected,
            }
        )

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

    # Retrieve relevant KB chunks
    try:
        kb_chunks = _get_kb_context(message)
    except Exception as kb_exc:
        kb_chunks = []
        print(f"[WARNING] KB retrieval failed: {kb_exc}")

    context_parts = [f"[{p['source']}]\n{p['text']}" for p in top_pages] if top_pages else []
    if kb_chunks:
        context_parts += [f"[KB: {c['source']}]\n{c['text']}" for c in kb_chunks]
    context_text = "\n\n---\n\n".join(context_parts)

    system_prompt = (
        "Você é um assistente especializado em análise de documentos e base de conhecimento. "
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
    if kb_chunks:
        used_sources += [f"KB: {c['source']}" for c in kb_chunks]

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
# POST /v1/nanobot-poc/odoo/webhook/crm/lead
# ---------------------------------------------------------------------------

class CRMLeadWebhookPayload(BaseModel):
    lead_id: int


@app.post(
    "/v1/nanobot-poc/odoo/webhook/crm/lead",
    summary="ODOO CRM Lead Webhook – process lead through AI Agent",
)
async def odoo_crm_lead_webhook(payload: CRMLeadWebhookPayload):
    """
    Receives an ODOO CRM webhook with a lead_id.
    - Checks if the lead is in the INITIAL stage.
    - Posts the agent message to the lead's chatter.
    - Moves the lead to the IN PROCESS stage.
    """
    lead_id = payload.lead_id
    uid, models_proxy = _odoo_connect()

    # Read lead's current stage
    try:
        lead_data = models_proxy.execute_kw(
            ODOO_DB, uid, ODOO_API_KEY,
            "crm.lead", "read",
            [[lead_id]],
            {"fields": ["name", "stage_id"]},
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to read lead {lead_id}: {exc}")

    if not lead_data:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found.")

    lead = lead_data[0]
    stage_id_val = lead.get("stage_id")
    current_stage_name = stage_id_val[1] if stage_id_val else ""

    if current_stage_name.upper() != ODOO_STAGE_INITIAL.upper():
        return JSONResponse({
            "status": "skipped",
            "lead_id": lead_id,
            "lead_name": lead.get("name"),
            "current_stage": current_stage_name,
            "message": (
                f"Lead is in stage '{current_stage_name}', "
                f"not '{ODOO_STAGE_INITIAL}'. No action taken."
            ),
        })

    # Post message to lead chatter
    try:
        models_proxy.execute_kw(
            ODOO_DB, uid, ODOO_API_KEY,
            "crm.lead", "message_post",
            [[lead_id]],
            {"body": AGENT_MESSAGE, "message_type": "comment"},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to post message to lead {lead_id}: {exc}",
        )

    # Resolve target stage ID dynamically (never hard-code IDs)
    try:
        stages = models_proxy.execute_kw(
            ODOO_DB, uid, ODOO_API_KEY,
            "crm.stage", "search_read",
            [[]],
            {"fields": ["id", "name"]},
        )
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Failed to retrieve stages: {exc}")

    target_stage = next(
        (s for s in stages if s["name"].upper() == ODOO_STAGE_IN_PROCESS.upper()), None
    )
    if not target_stage:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Stage '{ODOO_STAGE_IN_PROCESS}' not found. "
                f"Available: {[s['name'] for s in stages]}"
            ),
        )

    # Move lead to IN PROCESS stage
    try:
        models_proxy.execute_kw(
            ODOO_DB, uid, ODOO_API_KEY,
            "crm.lead", "write",
            [[lead_id]],
            {"stage_id": target_stage["id"]},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to update stage for lead {lead_id}: {exc}",
        )

    return JSONResponse({
        "status": "processed",
        "lead_id": lead_id,
        "lead_name": lead.get("name"),
        "previous_stage": current_stage_name,
        "new_stage": ODOO_STAGE_IN_PROCESS,
        "message_posted": AGENT_MESSAGE,
    })
