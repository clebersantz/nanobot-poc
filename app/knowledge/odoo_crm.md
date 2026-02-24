# Odoo CRM — Nanobot Knowledge File

## Your Mission

When you receive a **lead ID**, you must autonomously perform these steps **in order**:

1. **Read the lead** — fetch `id`, `name`, `stage_id`, and `partner_name` from `crm.lead`.
2. **Check the stage** — only proceed if the lead is in the **INITIAL** stage (stage name contains "initial", case-insensitive). If the stage is different, stop and report the current stage without making changes.
3. **Post a processing message** — add a message to the lead chatter saying:
   `"🤖 Nanobot: Lead recebido e em processamento."`
4. **Advance to IN PROGRESS** — find the stage whose name contains "in progress" (case-insensitive) and update the lead's `stage_id` to that stage's ID.
5. **Confirm** — report back with the lead name and the new stage name.

## Available Tools

Use the low-level XML-RPC tools to interact with Odoo:

### `odoo_search_read`
Search and read records from any Odoo model.
- `model`: e.g. `"crm.lead"`, `"crm.stage"`
- `domain`: filter list, e.g. `[["id", "=", 42]]` or `[["name", "ilike", "initial"]]`
- `fields`: list of field names to return, e.g. `["id", "name", "stage_id"]`

### `odoo_write`
Update fields on existing records.
- `model`: e.g. `"crm.lead"`
- `ids`: list of record IDs, e.g. `[42]`
- `values`: dict of fields to update, e.g. `{"stage_id": 3}`

### `odoo_message_post`
Post a message in the chatter of a record.
- `model`: e.g. `"crm.lead"`
- `record_id`: the integer ID of the record
- `body`: HTML or plain-text message body

## Odoo Data Model Reference

### crm.lead (CRM Leads/Opportunities)
Key fields:
- `id` (int) — record ID
- `name` (str) — lead title
- `partner_name` (str) — contact name
- `stage_id` (many2one → crm.stage) — returned as `[id, name]`

### crm.stage (CRM Pipeline Stages)
Key fields:
- `id` (int) — stage ID
- `name` (str) — stage name (e.g. "Initial", "In Progress", "Won")

## Stage Resolution Strategy

1. Use `odoo_search_read` on `crm.stage` with domain `[]` (all stages) and fields `["id", "name"]`.
2. Find the stage whose `name` contains "initial" (case-insensitive) to verify the lead is in the right stage.
3. Find the stage whose `name` contains "in progress" (case-insensitive) to get the target stage ID.

## Important Rules

- **Never skip the stage check.** If the lead is not in INITIAL, do nothing except report.
- **Always post the message before changing the stage.**
- **Use only the tools provided.** Do not guess field values; always read them from Odoo first.
- **Be precise.** Pass exact IDs returned by Odoo — do not invent IDs.
