# Agent Rules

Behavioural rules and guardrails for AI agents working with this knowledge base.

---

## 1. Always Verify Instance-Specific IDs

Stage IDs, activity type IDs, user IDs, and custom field names differ between Odoo instances.  
**Never hard-code IDs from examples.** Always resolve them via XML-RPC before use:

```python
# Resolve stage IDs
stages = models.execute_kw(db, uid, password,
    'crm.stage', 'search_read',
    [[]], {'fields': ['id', 'name'], 'order': 'sequence'})
```

---

## 2. Never Embed Real Credentials

All connection examples use placeholders (`<ODOO_URL>`, `<DB_NAME>`, `<USERNAME>`, `<PASSWORD>`).  
Credentials must be injected at runtime from environment variables or a secrets manager.

---

## 3. Confirm Before Destructive Operations

Before calling `write` or `unlink` on more than one record, confirm the record IDs by doing a `search_read` first and presenting the list to the user.

---

## 4. Use Minimal Field Sets

When calling `search_read` or `read`, specify only the fields you need via the `fields` parameter to reduce payload size and latency.

---

## 5. Respect Rate Limits

Odoo XML-RPC has no built-in rate limiting, but the host server may throttle requests.  
Add a short sleep (0.2 s) between bulk operations when processing more than 50 records.

---

## 6. Handle Errors Gracefully

Wrap every XML-RPC call in try/except. Map known fault codes to user-friendly messages using `docs/kb/20-odoo/06-errors/common-xmlrpc-errors.md`.

---

## 7. Prefer `search_read` over `search` + `read`

`search_read` is a single round-trip. Use it unless you need only IDs.

---

## 8. Domain Syntax

A domain is always a **list of triples**: `[[field, operator, value], ...]`.  
An empty domain `[]` matches all records. Use `['&', cond1, cond2]` for explicit AND.

---

## 9. Pagination for Large Result Sets

Always pass `limit` and `offset` when iterating large datasets:

```python
BATCH = 100
offset = 0
while True:
    batch = models.execute_kw(db, uid, password,
        'crm.lead', 'search_read',
        [domain], {'fields': fields, 'limit': BATCH, 'offset': offset})
    if not batch:
        break
    process(batch)
    offset += BATCH
```

---

## 10. Document Every Action Taken

When performing automated actions, log what was read, what was changed, and what IDs were affected so the user can audit the operation.
