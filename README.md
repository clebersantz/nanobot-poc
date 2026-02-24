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
| `CRM_AGENT_MAX_TURNS` | `10` | Número máximo de rodadas do agente IA |

---

## Integração Odoo CRM

O Nanobot usa um **agente de IA** (OpenAI tool-calling) para processar leads do Odoo CRM. Ao invés de executar passos fixos em código, o agente usa seu conhecimento para decidir quais ações executar.

### Como funciona o webhook (`POST /v1/crm/webhook`)

1. O usuário move um lead para o estágio **INITIAL** no Odoo e o Odoo dispara o webhook.
2. O Nanobot recebe `{"lead_id": 42}` e inicia um agente OpenAI com as seguintes ferramentas disponíveis:
   - `get_lead_info` — busca detalhes do lead (nome, estágio atual, etc.)
   - `list_crm_stages` — lista todos os estágios do pipeline
   - `post_message_on_lead` — posta uma mensagem no chatter do lead
   - `move_lead_to_stage` — move o lead para um novo estágio
3. O agente **inspeciona o lead**, verifica o estágio, posta `"Hello, processed by Nanobot"` e move o lead para **IN PROGRESS** — tudo decidido pela IA usando seu conhecimento de CRM.
4. A resposta inclui as ações executadas e um resumo em linguagem natural.

### Exemplo de chamada ao webhook

```bash
curl -X POST http://localhost:8000/v1/crm/webhook \
  -H "Content-Type: application/json" \
  -d '{"lead_id": 42}'
```

Resposta:
```json
{
  "lead_id": 42,
  "actions": [
    {"tool": "get_lead_info", "args": {"lead_id": 42}, "result": {"id": 42, "name": "Acme Corp", "stage_name": "INITIAL"}},
    {"tool": "post_message_on_lead", "args": {"lead_id": 42, "message": "Hello, processed by Nanobot"}, "result": {"lead_id": 42, "message_posted": "Hello, processed by Nanobot"}},
    {"tool": "move_lead_to_stage", "args": {"lead_id": 42, "stage_name": "IN PROGRESS"}, "result": {"lead_id": 42, "moved_to_stage": "IN PROGRESS"}}
  ],
  "summary": "Lead 42 (Acme Corp) was in the INITIAL stage. I posted the Nanobot message and moved it to IN PROGRESS."
}
```

### Processar todos os leads INITIAL de uma vez

```bash
curl -X POST http://localhost:8000/v1/crm/process-initial-leads
```
