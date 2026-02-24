# Process: Create a CRM Lead

## Purpose

Create a new lead record in `crm.lead` via XML-RPC.

---

## Inputs

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | ✓ | Lead title |
| `type` | string | — | `'lead'` (default) or `'opportunity'` |
| `contact_name` | string | — | Contact person name |
| `email_from` | string | — | Contact email |
| `phone` | string | — | Contact phone |
| `partner_name` | string | — | Company name |
| `partner_id` | int | — | Existing partner ID (overrides partner_name) |
| `user_id` | int | — | Salesperson user ID |
| `team_id` | int | — | Sales team ID |
| `stage_id` | int | — | Pipeline stage ID (verify first) |
| `priority` | string | — | `'0'`–`'3'` |
| `expected_revenue` | float | — | Deal value |
| `description` | string | — | Internal notes (HTML allowed) |
| `tag_ids` | list | — | `[[6, 0, [tag_id1, ...]]]` |

---

## Steps

### 1. Establish connection

See `docs/kb/20-odoo/01-connection/xmlrpc-connection.md`.

### 2. (Optional) Resolve stage ID

```python
stages = models.execute_kw(db, uid, password,
    'crm.stage', 'search_read',
    [[]], {'fields': ['id', 'name'], 'order': 'sequence'})
stage_id = next(s['id'] for s in stages if s['name'] == '<STAGE_NAME>')
```

### 3. Create the lead

```python
lead_id = models.execute_kw(db, uid, password,
    'crm.lead', 'create', [{
        'name': '<LEAD_TITLE>',
        'type': 'lead',
        'contact_name': '<CONTACT_NAME>',
        'email_from': '<EMAIL>',
        'phone': '<PHONE>',
        'partner_name': '<COMPANY>',
        'user_id': <SALESPERSON_ID>,
        'stage_id': <STAGE_ID>,
        'expected_revenue': <REVENUE>,
        'description': '<NOTES>',
    }])
print(f"Created lead ID: {lead_id}")
```

---

## Output

| Variable | Type | Description |
|---|---|---|
| `lead_id` | int | ID of the newly created lead |

---

## Validation

```python
lead = models.execute_kw(db, uid, password,
    'crm.lead', 'read', [[lead_id]],
    {'fields': ['name', 'type', 'email_from', 'stage_id', 'user_id']})
print(lead)
```

---

## Errors

| Error | Cause | Fix |
|---|---|---|
| `Missing required field: name` | `name` not provided | Always include `name` |
| `Access Denied` | User lacks CRM create permission | Check user group: CRM / User or above |
| `Invalid field <x>` | Typo in field name | Verify field name with `fields_get` |
| Many2one ID not found | Stage/user/team ID does not exist | Resolve IDs via `search_read` first |
