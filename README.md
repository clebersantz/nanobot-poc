# Nanobot POC

POC simples estilo "nanobot" em FastAPI com Docker para **chat** e **OCR de PDFs** (scans), usando OpenAI como LLM. Sem persistência de dados.

---

## Funcionalidades

| Endpoint | Descrição |
|---|---|
| `GET /` | UI HTML com chat e upload múltiplo de PDFs |
| `POST /v1/chat` | Recebe mensagem + PDFs, faz OCR, mini-retrieval por embeddings e responde via OpenAI |
| `POST /v1/ocr` | OCR puro das páginas (debug) |
| `POST /v1/crm/webhook` | Webhook: recebe `{"lead_id": <int>}` e processa o lead no Odoo CRM |
| `POST /v1/crm/process-initial-leads` | Processa todos os leads no estágio INITIAL do Odoo CRM |
| `GET /docs` | Swagger UI automático |

---

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

Para habilitar a integração com o Odoo CRM, adicione ao `.env`:

```
ODOO_URL=https://mycompany.odoo.com
ODOO_DB=mydb
ODOO_USERNAME=admin
ODOO_PASSWORD=mypassword
ODOO_INITIAL_STAGE=INITIAL        # opcional, padrão: INITIAL
ODOO_IN_PROGRESS_STAGE=IN PROGRESS # opcional, padrão: IN PROGRESS
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
| `ODOO_URL` | *(obrigatório para CRM)* | URL base da instância Odoo |
| `ODOO_DB` | *(obrigatório para CRM)* | Nome do banco de dados Odoo |
| `ODOO_USERNAME` | *(obrigatório para CRM)* | Usuário de login Odoo |
| `ODOO_PASSWORD` | *(obrigatório para CRM)* | Senha ou API key do Odoo |
| `ODOO_INITIAL_STAGE` | `INITIAL` | Nome do estágio inicial do CRM |
| `ODOO_IN_PROGRESS_STAGE` | `IN PROGRESS` | Nome do estágio "em andamento" do CRM |

---

## Integração Odoo CRM

O Nanobot pode se integrar ao Odoo CRM via XML-RPC para:

1. **Processar leads pelo webhook** (`POST /v1/crm/webhook`):
   - Recebe `{"lead_id": 42}` via HTTP POST
   - Posta a mensagem `"Hello, processed by Nanobot"` no lead
   - Move o lead para o estágio **IN PROGRESS**

2. **Processar todos os leads no estágio INITIAL** (`POST /v1/crm/process-initial-leads`):
   - Busca todos os leads no estágio **INITIAL**
   - Para cada lead: posta a mensagem e move para **IN PROGRESS**

### Exemplo de chamada ao webhook

```bash
curl -X POST http://localhost:8000/v1/crm/webhook \
  -H "Content-Type: application/json" \
  -d '{"lead_id": 42}'
```

Resposta:
```json
{"lead_id": 42, "status": "processed"}
```
