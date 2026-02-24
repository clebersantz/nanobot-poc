# Nanobot POC – Knowledge Base

This directory contains the knowledge base (KB) for the Nanobot POC AI agent. The KB is structured for use with [nanobot.ai](https://github.com/nanobot-ai/nanobot) and covers Odoo 18 CRM Leads automation via XML-RPC.

---

## Directory Structure

```
docs/
├── README.md               ← this file
├── kb-manifest.yaml        ← indexing manifest for nanobot.ai
└── kb/
    ├── 00-meta/            ← Glossary & agent rules
    ├── 20-odoo/
    │   ├── 01-connection/  ← XML-RPC connection guide
    │   ├── 02-models/      ← Model reference (crm.lead, mail.activity, etc.)
    │   ├── 03-fields/      ← Field reference & custom fields
    │   ├── 04-processes/   ← Step-by-step process guides
    │   ├── 05-runbooks/    ← Operational runbooks
    │   └── 06-errors/      ← Error reference
```

---

## How to Use This Knowledge Base with nanobot.ai

### 1. Upload / Connect the `docs/kb/` Directory

In nanobot.ai, create a new **Knowledge Base** and upload all Markdown files from `docs/kb/`:

```
docs/kb/**/*.md
```

Or connect your repository directly if nanobot.ai supports GitHub integration.

---

### 2. Index the Knowledge Base

Use `docs/kb-manifest.yaml` as the indexing configuration.  
Key settings (adjust to your needs):

| Setting | Default | Description |
|---|---|---|
| `chunk_size` | 512 | Tokens per chunk |
| `chunk_overlap` | 64 | Overlap between chunks |
| `top_k` | 5 | Chunks retrieved per query |

Trigger indexing via the nanobot.ai UI or CLI:

```bash
nanobot index --manifest docs/kb-manifest.yaml
```

Wait for indexing to complete before testing.

---

### 3. Attach the KB to Your Agent

In nanobot.ai, open your agent configuration and attach the indexed knowledge base collection(s) from `kb-manifest.yaml`. You can attach individual collections (e.g., only `kb-odoo-processes`) or all of them.

---

### 4. Configure the Agent System Prompt

Instruct the agent to use this KB for Odoo CRM tasks. Example system prompt addition:

```
You are an Odoo 18 CRM automation assistant. Use the attached knowledge base
to answer questions about XML-RPC integration, crm.lead operations, and
sales pipeline management. Always verify instance-specific IDs (stage IDs,
user IDs, activity type IDs) via XML-RPC before using them.
```

---

### 5. Test the Agent

Try these test queries after attaching the KB:

| Query | Expected behaviour |
|---|---|
| "How do I connect to Odoo via XML-RPC?" | Returns connection steps from `01-connection/xmlrpc-connection.md` |
| "What fields does crm.lead have?" | Returns field list from `03-fields/crm-lead-fields.md` |
| "How do I create a lead?" | Returns steps from `04-processes/create-lead.md` |
| "What does 'Access Denied' mean in XML-RPC?" | Returns fix from `06-errors/common-xmlrpc-errors.md` |
| "How do I deduplicate leads by email?" | Returns runbook from `05-runbooks/deduplicate-by-email.md` |

---

## Maintaining the Knowledge Base

- **Add new processes** as Markdown files in `docs/kb/20-odoo/04-processes/`.
- **Update field docs** when custom fields are added to the Odoo instance.
- **Re-index** after any additions or updates using the manifest.
- **All placeholders** (`<ANGLE_BRACKETS>`) in the docs must be replaced with real values before executing any example code against your Odoo instance.
