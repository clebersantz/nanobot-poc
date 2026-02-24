# Nanobot Knowledge: Odoo CRM via XML-RPC

This document is your knowledge base for interacting with Odoo CRM.
Use the generic Odoo tools (`odoo_search`, `odoo_read`, `odoo_write`, `odoo_call`)
together with the information below to complete any CRM task.

---

## Authentication

Authentication is handled automatically by the environment. You do **not** need to
authenticate explicitly — the Odoo tools are pre-configured with the credentials from
the environment variables (`ODOO_URL`, `ODOO_DB`, `ODOO_USERNAME`, `ODOO_PASSWORD`).

---

## Key Odoo Models

### `crm.lead`
Represents a CRM lead or opportunity.

Commonly used fields:
| Field | Type | Description |
|---|---|---|
| `id` | integer | Unique record ID |
| `name` | string | Lead title / subject |
| `stage_id` | many2one `[id, name]` | Current pipeline stage |
| `partner_id` | many2one `[id, name]` | Related contact / company |
| `user_id` | many2one `[id, name]` | Assigned salesperson |
| `description` | string | Internal notes |
| `probability` | float | Win probability (%) |

### `crm.stage`
Represents a pipeline stage.

Commonly used fields:
| Field | Type | Description |
|---|---|---|
| `id` | integer | Unique record ID |
| `name` | string | Stage label (e.g. "INITIAL", "IN PROGRESS") |
| `sequence` | integer | Order in the pipeline |

---

## How to Find a Stage ID by Name

Use `odoo_search` on the `crm.stage` model with an `ilike` domain filter.
Stage names are matched case-insensitively.

**Example — find the "INITIAL" stage:**
```
odoo_search(model="crm.stage", domain=[["name", "ilike", "INITIAL"]], limit=1)
# Returns: [4]   (list of matching IDs)
```

**Example — find the "IN PROGRESS" stage:**
```
odoo_search(model="crm.stage", domain=[["name", "ilike", "IN PROGRESS"]], limit=1)
# Returns: [7]
```

---

## How to Find All Leads in the INITIAL Stage

First resolve the stage ID (see above), then search `crm.lead`:

```
# Step 1 — get stage id
stage_ids = odoo_search(model="crm.stage", domain=[["name", "ilike", "INITIAL"]], limit=1)
# stage_ids = [4]

# Step 2 — find leads in that stage
lead_ids = odoo_search(model="crm.lead", domain=[["stage_id", "=", 4]])
# lead_ids = [101, 102, 103]
```

---

## How to Read Lead Details

Use `odoo_read` to fetch specific fields for a list of IDs:

```
leads = odoo_read(
    model="crm.lead",
    ids=[101],
    fields=["id", "name", "stage_id", "partner_id"]
)
# Returns: [{"id": 101, "name": "Acme Corp", "stage_id": [4, "INITIAL"], ...}]
```

Note: many2one fields like `stage_id` are returned as `[id, name]` pairs.

---

## How to Post a Message (Chatter Note) on a Lead

Use `odoo_call` with method `message_post` on `crm.lead`:

```
odoo_call(
    model="crm.lead",
    method="message_post",
    args=[[101]],
    kwargs={
        "body": "Hello, processed by Nanobot",
        "message_type": "comment",
        "subtype_xmlid": "mail.mt_note"
    }
)
```

---

## How to Move a Lead to a Different Stage

Use `odoo_write` to update the `stage_id` field:

```
# First resolve the target stage id, e.g. in_progress_stage_id = 7
odoo_write(
    model="crm.lead",
    ids=[101],
    values={"stage_id": 7}
)
```

---

## Standard CRM Workflow: Process a Lead from INITIAL to IN PROGRESS

When you receive a lead ID and need to process it:

1. **Read lead details** — call `odoo_read` on `crm.lead` with `fields=["id", "name", "stage_id"]`
   to get the current stage.
2. **Check stage** — read the stage name from `stage_id[1]`.
3. **If the lead is in the INITIAL stage:**
   a. Post the message `"Hello, processed by Nanobot"` using `odoo_call` → `message_post`.
   b. Find the IN PROGRESS stage ID with `odoo_search` on `crm.stage`.
   c. Move the lead with `odoo_write` → `stage_id = <in_progress_id>`.
4. **If the lead is NOT in the INITIAL stage:** report that no action was taken and explain the current stage.

---

## Standard CRM Workflow: Process All Leads in the INITIAL Stage

1. Find the INITIAL stage ID: `odoo_search(model="crm.stage", domain=[["name", "ilike", "INITIAL"]], limit=1)`
2. Find all lead IDs in that stage: `odoo_search(model="crm.lead", domain=[["stage_id", "=", <initial_id>]])`
3. If no leads are found, report that the queue is empty.
4. For each lead ID — follow the "Process a Lead from INITIAL to IN PROGRESS" workflow above.
   Resolve the IN PROGRESS stage ID **once** before the loop.

---

## Environment Variables (pre-configured, do not hardcode values)

| Variable | Purpose |
|---|---|
| `ODOO_URL` | Base URL of the Odoo instance |
| `ODOO_DB` | Database name |
| `ODOO_USERNAME` | Login username |
| `ODOO_PASSWORD` | Password or API key |
