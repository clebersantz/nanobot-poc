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
| `CRM_AGENT_MAX_TURNS` | `10` | Número máximo de rodadas do agente IA |

---

## Integração Odoo CRM — baseada em conhecimento (Knowledge-driven)

O Nanobot usa um **agente de IA** (OpenAI tool-calling) alimentado por uma **base de conhecimento** para interagir com o Odoo CRM. Não há lógica de negócio codificada — o agente aprende *o que fazer* a partir do arquivo de conhecimento e decide autonomamente quais chamadas de API realizar.

### Arquitetura

```
Webhook / endpoint
       │
       ▼
  Nanobot Agent (OpenAI gpt-4o-mini)
       │  carrega
       ├──► app/knowledge/odoo_crm.md   ← base de conhecimento
       │
       │  usa ferramentas genéricas
       ├──► odoo_search  — busca registros por filtro (crm.lead, crm.stage …)
       ├──► odoo_read    — lê campos de registros
       ├──► odoo_write   — escreve campos em registros
       └──► odoo_call    — chama qualquer método do modelo (ex: message_post)
```

O arquivo `app/knowledge/odoo_crm.md` ensina ao agente:
- Como autenticar no Odoo (via variáveis de ambiente pré-configuradas)
- Os modelos relevantes (`crm.lead`, `crm.stage`) e seus campos
- Como buscar leads por estágio
- Como postar mensagens no chatter
- Como mover leads entre estágios
- O fluxo padrão de processamento: INITIAL → mensagem → IN PROGRESS

### Como funciona o webhook (`POST /v1/crm/webhook`)

1. O usuário move um lead para o estágio **INITIAL** no Odoo e o Odoo dispara o webhook.
2. O Nanobot recebe `{"lead_id": 42}` e inicia o agente com sua base de conhecimento.
3. O agente usa `odoo_read` para inspecionar o lead, `odoo_call` para postar a mensagem e `odoo_write` para mover o estágio — **tudo decidido pela IA com base no conhecimento**.
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
    {"tool": "odoo_read",  "args": {"model": "crm.lead", "ids": [42], "fields": ["id", "name", "stage_id"]}, "result": [{"id": 42, "name": "Acme Corp", "stage_id": [4, "INITIAL"]}]},
    {"tool": "odoo_call",  "args": {"model": "crm.lead", "method": "message_post", "args": [[42]], "kwargs": {"body": "Hello, processed by Nanobot", "message_type": "comment", "subtype_xmlid": "mail.mt_note"}}, "result": 123},
    {"tool": "odoo_search","args": {"model": "crm.stage", "domain": [["name", "ilike", "IN PROGRESS"]], "limit": 1}, "result": [7]},
    {"tool": "odoo_write", "args": {"model": "crm.lead", "ids": [42], "values": {"stage_id": 7}}, "result": true}
  ],
  "summary": "Lead 42 (Acme Corp) was in the INITIAL stage. I posted 'Hello, processed by Nanobot' and moved it to IN PROGRESS."
}
```

### Processar todos os leads INITIAL de uma vez

```bash
curl -X POST http://localhost:8000/v1/crm/process-initial-leads
```

### Estender o conhecimento do Nanobot

Para ensinar ao Nanobot novas tarefas de CRM, edite o arquivo `app/knowledge/odoo_crm.md`. Nenhuma alteração de código é necessária — o agente carrega o arquivo na inicialização.
