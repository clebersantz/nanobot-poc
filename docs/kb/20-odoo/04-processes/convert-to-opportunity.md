# Process: Convert Lead to Opportunity

## Purpose

Convert a `crm.lead` of type `'lead'` into an `'opportunity'` by assigning a pipeline stage, salesperson, and optionally linking or creating a customer partner.

---

## Inputs

| Parameter | Type | Required | Description |
|---|---|---|---|
| `lead_id` | int | ✓ | ID of the lead to convert |
| `stage_id` | int | ✓ | Target pipeline stage ID |
| `user_id` | int | — | Salesperson ID (defaults to current user) |
| `partner_id` | int | — | Existing partner ID to link |
| `partner_name` | string | — | Company name (if creating a new partner) |
| `contact_name` | string | — | Contact name (if creating a new partner) |

---

## Steps

### 1. Establish connection

See `docs/kb/20-odoo/01-connection/xmlrpc-connection.md`.

### 2. Verify the lead is of type 'lead'

```python
lead = models.execute_kw(db, uid, password,
    'crm.lead', 'read', [[<LEAD_ID>]],
    {'fields': ['name', 'type', 'email_from', 'partner_id']})
assert lead[0]['type'] == 'lead', "Record is already an opportunity."
```

### 3. Resolve stage ID

```python
stages = models.execute_kw(db, uid, password,
    'crm.stage', 'search_read',
    [[]], {'fields': ['id', 'name'], 'order': 'sequence'})

target_stage_name = '<FIRST_OPPORTUNITY_STAGE>'  # e.g. 'New' or 'Qualified'
stage = next(s for s in stages if s['name'] == target_stage_name)
stage_id = stage['id']
```

### 4. Find or create a partner (optional)

```python
# Search for existing partner by email
existing = models.execute_kw(db, uid, password,
    'res.partner', 'search_read',
    [[['email', '=', lead[0]['email_from']]]],
    {'fields': ['id', 'name']})

if existing:
    partner_id = existing[0]['id']
    print(f"Linking existing partner: {existing[0]['name']}")
else:
    partner_id = models.execute_kw(db, uid, password,
        'res.partner', 'create', [{
            'name': '<CONTACT_NAME>',
            'email': lead[0]['email_from'],
            'is_company': False,
        }])
    print(f"Created new partner with ID: {partner_id}")
```

### 5. Convert the lead

```python
models.execute_kw(db, uid, password,
    'crm.lead', 'write',
    [[<LEAD_ID>]], {
        'type': 'opportunity',
        'stage_id': stage_id,
        'partner_id': partner_id,
        'user_id': <SALESPERSON_ID>,
    })
print(f"Lead {<LEAD_ID>} converted to opportunity.")
```

> **Note:** For a full conversion workflow (deduplication, merge), use the native Odoo action `crm.lead` → `convert_opportunity` if exposed via RPC, or perform the steps above manually.

---

## Output

| Effect | Description |
|---|---|
| `type` changed | Lead is now `'opportunity'` |
| `stage_id` set | Lead is in the sales pipeline |
| `partner_id` linked | Customer linked or created |
| `date_open` set | Odoo sets this automatically |

---

## Validation

```python
opp = models.execute_kw(db, uid, password,
    'crm.lead', 'read', [[<LEAD_ID>]],
    {'fields': ['name', 'type', 'stage_id', 'partner_id', 'user_id', 'date_open']})
print(opp)
```

---

## Errors

| Error | Cause | Fix |
|---|---|---|
| Already an opportunity | `type` already `'opportunity'` | Skip conversion |
| Stage not found | Stage name mismatch | List and verify stages |
| `Access Denied` | Insufficient permissions | Ensure CRM User or Manager role |
