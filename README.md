# Nanobot POC

POC simples estilo "nanobot" em FastAPI com Docker para **chat** e **OCR de PDFs** (scans), usando OpenAI como LLM. Sem persistência de dados.

---

## Funcionalidades

| Endpoint | Descrição |
|---|---|
| `GET /` | UI HTML com chat e upload múltiplo de PDFs |
| `POST /v1/chat` | Recebe mensagem + PDFs, faz OCR, mini-retrieval por embeddings e responde via OpenAI |
| `POST /v1/ocr` | OCR puro das páginas (debug) |
| `POST /v1/nanobot-poc/odoo/webhook/crm/lead` | Webhook ODOO CRM para processar leads |
| `GET /docs` | Swagger UI automático |

---

Workflow ODOO CRM configurado em `docs/workflow/crm_lead.md`.

## Pré-requisitos

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows/WSL ou Linux)
- Chave de API da OpenAI

---

## Execução (Windows / WSL + Docker)

### 1. Clone o repositório

```bash
git clone https://github.com/clebersantz/nanobot-poc.git
cd nanobot-poc
```

### 2. Crie o arquivo `.env`

```bash
# Windows (PowerShell)
echo OPENAI_API_KEY=sk-... > .env

# Linux / WSL / macOS
echo "OPENAI_API_KEY=sk-..." > .env
```

> ⚠️ O arquivo `.env` está no `.gitignore` e **nunca** deve ser commitado.

Variáveis opcionais (com defaults):

```
MAX_PAGES_PER_PDF=5   # Máximo de páginas processadas por PDF
TOP_K_PAGES=3         # Quantas páginas mais relevantes enviar ao LLM
```

### 3. Suba o container

```bash
docker compose up --build
```

### 4. Acesse

- **Chat:** http://localhost:8000/
- **Swagger:** http://localhost:8000/docs

---

## Troubleshooting

| Problema | Solução |
|---|---|
| `AuthenticationError` / 401 | Verifique se `OPENAI_API_KEY` está correto no `.env` |
| OCR muito lento | Reduza `MAX_PAGES_PER_PDF` no `.env` (ex.: `MAX_PAGES_PER_PDF=2`) |
| Resposta sem contexto | O PDF pode ser nativo (não scan). Teste com um PDF de imagem/scan |
| Erro de porta 8000 | Altere a porta no `docker-compose.yml` (ex.: `"8001:8000"`) |

---

## Variáveis de ambiente

| Variável | Default | Descrição |
|---|---|---|
| `OPENAI_API_KEY` | *(obrigatório)* | Chave de API da OpenAI |
| `MAX_PAGES_PER_PDF` | `5` | Máximo de páginas por PDF para OCR |
| `TOP_K_PAGES` | `3` | Top-K páginas mais relevantes enviadas ao LLM |
| `ODOO_URL` | *(obrigatório para ODOO)* | URL base do ODOO (ex.: `https://odoo.suaempresa.com`) |
| `ODOO_DB` | *(obrigatório para ODOO)* | Nome do banco de dados do ODOO |
| `ODOO_USER` | *(obrigatório para ODOO)* | Usuário do ODOO |
| `ODOO_API_KEY` | *(obrigatório para ODOO)* | API Key do usuário ODOO para XML-RPC |
| `ODOO_WORKFLOW_PATH` | `docs/kb` | Caminho da base de conhecimento do ODOO (arquivo ou diretório) |
| `ODOO_WORKFLOW_AI_MODEL` | `gpt-4o-mini` | Modelo OpenAI usado para interpretar o workflow do ODOO |
| `ODOO_WORKFLOW_MAX_SECTIONS` | `2` | Máximo de trechos do workflow usados como base de conhecimento |
