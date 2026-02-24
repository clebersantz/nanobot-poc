import math
import os
import re
import tempfile
import xmlrpc.client
from typing import List, Optional, Tuple

import pytesseract
from pdf2image import convert_from_path
from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from openai import OpenAI
from pydantic import BaseModel

MAX_PAGES_PER_PDF = int(os.getenv("MAX_PAGES_PER_PDF", "5"))
TOP_K_PAGES = int(os.getenv("TOP_K_PAGES", "3"))
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_ODOO_WORKFLOW_PATH = os.path.join(
    BASE_DIR,
    "docs",
    "workflow",
    "crm_lead.md",
)
ODOO_WORKFLOW_PATH = os.getenv("ODOO_WORKFLOW_PATH", DEFAULT_ODOO_WORKFLOW_PATH)
# Regex patterns are module-level to avoid recompilation on each webhook call.
# Workflow parsing expects the exact English phrases defined in docs/workflow/crm_lead.md.
ODOO_CASE_PATTERN = re.compile(r"Case CRM Lead stage is\s+(.+):", re.IGNORECASE)
ODOO_NOTE_PATTERN = re.compile(r'Add a Lead note\s+"(.+)"', re.IGNORECASE)
ODOO_MOVE_PATTERN = re.compile(r"Move Lead to stage\s+(.+?)(?:\.)?$", re.IGNORECASE)

app = FastAPI(title="Nanobot POC", description="Chat + OCR de PDFs via OpenAI")

client = OpenAI()  # reads OPENAI_API_KEY from env automatically


class OdooLeadWebhook(BaseModel):
    lead_id: int


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


def _load_odoo_workflow() -> dict:
    try:
        with open(ODOO_WORKFLOW_PATH, "r", encoding="utf-8") as handle:
            content = handle.read()
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail=f"Arquivo de conhecimento do workflow do Odoo não encontrado: {ODOO_WORKFLOW_PATH}",
        )

    workflow: dict = {}
    current_stage: Optional[str] = None
    unmatched_lines: List[str] = []
    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        # Skip markdown headers/preamble in the workflow file.
        if line.startswith("#"):
            continue
        case_match = ODOO_CASE_PATTERN.match(line)
        if case_match:
            current_stage = case_match.group(1).strip()
            workflow[current_stage] = {"message": None, "next_stage": None}
            continue
        if not current_stage:
            # Ignore any lines before the first stage definition.
            continue
        note_match = ODOO_NOTE_PATTERN.match(line)
        if note_match:
            workflow[current_stage]["message"] = note_match.group(1).strip()
            continue
        move_match = ODOO_MOVE_PATTERN.match(line)
        if move_match:
            workflow[current_stage]["next_stage"] = move_match.group(1).strip()
            continue
        unmatched_lines.append(f"linha {line_number}: {line}")

    if not workflow:
        raise HTTPException(
            status_code=500,
            detail=f"Arquivo de conhecimento do workflow do Odoo inválido: {ODOO_WORKFLOW_PATH}",
        )
    missing = [
        stage
        for stage, data in workflow.items()
        if not data.get("message") or not data.get("next_stage")
    ]
    if missing:
        raise HTTPException(
            status_code=500,
            detail=(
                "Arquivo de conhecimento do workflow do Odoo incompleto para estágios: "
                + ", ".join(sorted(missing))
            ),
        )
    if unmatched_lines:
        raise HTTPException(
            status_code=500,
            detail=(
                "Arquivo de conhecimento do workflow do Odoo possui linhas inválidas: "
                + "; ".join(unmatched_lines)
            ),
        )
    return workflow


def _get_odoo_connection():
    env_map = {
        "ODOO_URL": os.getenv("ODOO_URL"),
        "ODOO_DB": os.getenv("ODOO_DB"),
        "ODOO_USER": os.getenv("ODOO_USER"),
        "ODOO_API_KEY": os.getenv("ODOO_API_KEY"),
    }
    missing = [name for name, value in env_map.items() if not value]
    if missing:
        raise HTTPException(status_code=500, detail=f"Variáveis de ambiente ODOO ausentes: {', '.join(missing)}")
    common = xmlrpc.client.ServerProxy(f"{env_map['ODOO_URL']}/xmlrpc/2/common")
    uid = common.authenticate(env_map["ODOO_DB"], env_map["ODOO_USER"], env_map["ODOO_API_KEY"], {})
    if not uid:
        raise HTTPException(status_code=502, detail="Falha ao autenticar no ODOO.")
    models = xmlrpc.client.ServerProxy(f"{env_map['ODOO_URL']}/xmlrpc/2/object")
    return models, env_map["ODOO_DB"], uid, env_map["ODOO_API_KEY"]


def _get_lead_stage(
    models: xmlrpc.client.ServerProxy,
    db: str,
    uid: int,
    api_key: str,
    lead_id: int,
) -> Optional[Tuple[int, str]]:
    leads = models.execute_kw(db, uid, api_key, "crm.lead", "read", [[lead_id], ["stage_id"]])
    if not leads:
        return None
    stage = leads[0].get("stage_id")
    if isinstance(stage, list) and len(stage) >= 2:
        return stage[0], stage[1]
    return None


def _get_stage_id(
    models: xmlrpc.client.ServerProxy,
    db: str,
    uid: int,
    api_key: str,
    stage_name: str,
) -> Optional[int]:
    stage_ids = models.execute_kw(
        db,
        uid,
        api_key,
        "crm.stage",
        "search",
        [[["name", "=", stage_name]]],
        {"limit": 1},
    )
    return stage_ids[0] if stage_ids else None


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
# POST /v1/nanobot-poc/odoo/webhook/crm/lead
# ---------------------------------------------------------------------------

@app.post("/v1/nanobot-poc/odoo/webhook/crm/lead", summary="Webhook ODOO CRM Lead")
def odoo_crm_lead_webhook(payload: OdooLeadWebhook):
    workflow = _load_odoo_workflow()
    models, db, uid, api_key = _get_odoo_connection()
    try:
        lead_stage = _get_lead_stage(models, db, uid, api_key, payload.lead_id)
    except (xmlrpc.client.Fault, xmlrpc.client.ProtocolError):
        raise HTTPException(status_code=502, detail="Erro ao consultar lead no ODOO.")

    if not lead_stage:
        raise HTTPException(status_code=404, detail="Lead não encontrado no ODOO.")

    _, stage_name = lead_stage
    stage_rules = workflow.get(stage_name)
    if not stage_rules:
        return JSONResponse(
            {"status": "ignored", "lead_id": payload.lead_id, "current_stage": stage_name}
        )

    next_stage_name = stage_rules["next_stage"]
    try:
        next_stage_id = _get_stage_id(models, db, uid, api_key, next_stage_name)
    except (xmlrpc.client.Fault, xmlrpc.client.ProtocolError):
        raise HTTPException(status_code=502, detail="Erro ao buscar estágio no ODOO.")
    if not next_stage_id:
        raise HTTPException(
            status_code=404,
            detail=f"Stage '{next_stage_name}' não encontrado no ODOO.",
        )

    try:
        models.execute_kw(
            db,
            uid,
            api_key,
            "crm.lead",
            "message_post",
            [[payload.lead_id], {"body": stage_rules["message"]}],
        )
    except (xmlrpc.client.Fault, xmlrpc.client.ProtocolError):
        raise HTTPException(status_code=502, detail="Erro ao registrar mensagem no ODOO.")

    try:
        models.execute_kw(
            db,
            uid,
            api_key,
            "crm.lead",
            "write",
            [[payload.lead_id], {"stage_id": next_stage_id}],
        )
    except (xmlrpc.client.Fault, xmlrpc.client.ProtocolError):
        raise HTTPException(status_code=502, detail="Erro ao atualizar estágio do lead no ODOO.")

    return JSONResponse(
        {
            "status": "processed",
            "lead_id": payload.lead_id,
            "from_stage": stage_name,
            "to_stage": next_stage_name,
        }
    )
