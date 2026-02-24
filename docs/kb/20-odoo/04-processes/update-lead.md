# Process: Update a CRM Lead

## Purpose

Modify one or more fields on an existing `crm.lead` record via XML-RPC.

---

## Inputs

| Parameter | Type | Required | Description |
|---|---|---|---|
| `lead_id` | int | ✓ | ID of the lead to update |
| `values` | dict | ✓ | Field-value pairs to update |

---

## Steps

### 1. Establish connection

See `docs/kb/20-odoo/01-connection/xmlrpc-connection.md`.

### 2. Read current state (recommended before write)

```python
current = models.execute_kw(db, uid, password,
    'crm.lead', 'read', [[<LEAD_ID>]],
    {'fields': ['name', 'stage_id', 'user_id', 'probability', 'expected_revenue']})
print("Before:", current)
```

### 3. Update the lead

```python
success = models.execute_kw(db, uid, password,
    'crm.lead', 'write',
    [[<LEAD_ID>]],
    {
        'name': '<NEW_TITLE>',            # include only fields to change
        'expected_revenue': <NEW_VALUE>,
        'priority': '<0|1|2|3>',
        'description': '<UPDATED_NOTES>',
    })
# Returns True on success
```

### Batch update (multiple leads at once)

```python
# Update multiple leads with the same values
lead_ids = [<ID1>, <ID2>, <ID3>]
models.execute_kw(db, uid, password,
    'crm.lead', 'write',
    [lead_ids],
    {'user_id': <NEW_SALESPERSON_ID>})
```

---

## Output

| Value | Type | Description |
|---|---|---|
| `True` | bool | Write succeeded |
| `False` | bool | Write failed silently (rare) |

---

## Validation

```python
updated = models.execute_kw(db, uid, password,
    'crm.lead', 'read', [[<LEAD_ID>]],
    {'fields': ['name', 'stage_id', 'user_id', 'probability', 'expected_revenue']})
print("After:", updated)
```

---

## Errors

| Error | Cause | Fix |
|---|---|---|
| `Access Denied` | User lacks write permission | Check CRM group |
| `Record does not exist` | Wrong `lead_id` | Verify ID with `search_read` |
| `Invalid field <x>` | Typo in field name | Use `fields_get` to verify |
| `Validation error` | Value violates a constraint | Check allowed values for selection fields |
