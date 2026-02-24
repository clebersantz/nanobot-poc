# Common XML-RPC Errors

Reference for errors encountered when integrating with Odoo 18 via XML-RPC.

---

## Authentication Errors

### `authenticate` returns `False`

**Cause:** Wrong URL, database name, username, or password/API key.

**Fix:**
1. Verify `url` points to the correct Odoo instance (include scheme: `https://`).
2. Confirm the database name — visible on the Odoo login page or at `<url>/web/database/selector`.
3. Confirm the username (usually an email address).
4. If using a password, try generating an API key instead: Odoo → Settings → My Profile → API Keys.

---

## Access / Permission Errors

### `xmlrpc.client.Fault: Access Denied`

**Cause:** The authenticated user does not have permission to perform the operation.

**Fix:** Check the user's CRM group in Odoo → Settings → Users & Companies → Users:
- Read leads: CRM / User (Own Documents)
- Read all leads: CRM / User (All Documents) or CRM / Manager
- Create/write/unlink: CRM / User or CRM / Manager

---

### `xmlrpc.client.Fault: You are not allowed to access 'crm.lead' objects`

**Cause:** The user group does not include CRM model access.

**Fix:** Assign the user to the appropriate CRM security group.

---

## Validation Errors

### `xmlrpc.client.Fault: Odoo Server Error – Field … required`

**Cause:** A required field was not provided on `create`.

**Fix:** Always include `name` for `crm.lead`. Check `fields_get` with `attributes=['required']` to list all required fields.

---

### `xmlrpc.client.Fault: Invalid field … on model crm.lead`

**Cause:** Typo in field name or field does not exist on this Odoo version.

**Fix:**
```python
fields = models.execute_kw(db, uid, password,
    'crm.lead', 'fields_get', [],
    {'attributes': ['string', 'type']})
# Check if field name exists in fields.keys()
```

---

### `xmlrpc.client.Fault: Value error on field …`

**Cause:** Value does not match the expected type or selection options.

**Fix:** For `selection` fields, read allowed values:
```python
meta = models.execute_kw(db, uid, password,
    'crm.lead', 'fields_get',
    [['<FIELD_NAME>']], {'attributes': ['selection']})
allowed = meta['<FIELD_NAME>']['selection']  # list of [key, label]
```

---

## Record Not Found Errors

### `xmlrpc.client.Fault: … does not exist`

**Cause:** The record ID passed to `read`, `write`, or `unlink` does not exist (deleted or wrong ID).

**Fix:** Use `search_read` to verify the record exists before operating on it. Remember that archived records (`active=False`) are not returned by default — add `['active', 'in', [True, False]]` to the domain if needed.

---

## Connection / Transport Errors

### `ConnectionRefusedError` / `socket.gaierror`

**Cause:** The Odoo server is unreachable (wrong URL, server down, firewall).

**Fix:** Test connectivity: `curl -I <ODOO_URL>/xmlrpc/2/common`

---

### `xmlrpc.client.ProtocolError: 301 Moved Permanently`

**Cause:** HTTP URL redirects to HTTPS.

**Fix:** Use `https://` in `<ODOO_URL>`.

---

### `xmlrpc.client.ProtocolError: 404 Not Found`

**Cause:** Wrong endpoint path.

**Fix:** Ensure paths are `/xmlrpc/2/common` and `/xmlrpc/2/object` (not `/xmlrpc/common`).

---

## Timeout / Performance Issues

### Operation times out or is very slow

**Cause:** Domain returns too many records, or server is under load.

**Fix:**
- Add `limit` and `offset` for pagination.
- Narrow the domain with additional filters.
- Specify only needed fields with `'fields': [...]`.

---

## Many2one / Relational Errors

### Assigning a many2one with a non-existent ID

**Symptom:** `False` or empty value after write, or a Fault about record not found.

**Fix:** Always resolve IDs with `search_read` before passing them to `write` or `create`.

---

## Many2many Write Syntax

Many2many fields require special commands:

| Command | Syntax | Description |
|---|---|---|
| Replace all | `[[6, 0, [id1, id2]]]` | Set the field to exactly these IDs |
| Add | `[[4, id, 0]]` | Add a single ID |
| Remove | `[[3, id, 0]]` | Remove a single ID |
| Clear | `[[5, 0, 0]]` | Remove all |
