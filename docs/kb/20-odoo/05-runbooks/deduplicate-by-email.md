# Runbook: Deduplicate Leads by Email

## Purpose

Identify and handle duplicate `crm.lead` records that share the same `email_from` address to keep the CRM clean.

---

## Inputs

| Parameter | Type | Required | Description |
|---|---|---|---|
| `email` | string | ✓ | Email address to check for duplicates |

---

## Steps

### 1. Establish connection

See `docs/kb/20-odoo/01-connection/xmlrpc-connection.md`.

### 2. Search for leads with the same email

```python
email = '<EMAIL_ADDRESS>'

leads = models.execute_kw(db, uid, password,
    'crm.lead', 'search_read',
    [[['email_from', '=ilike', email], ['active', '=', True]]],
    {'fields': ['id', 'name', 'type', 'stage_id', 'user_id',
                'email_from', 'create_date', 'probability'],
     'order': 'create_date asc'})

print(f"Found {len(leads)} lead(s) with email '{email}':")
for lead in leads:
    print(f"  id={lead['id']}  name={lead['name']!r}  "
          f"type={lead['type']}  stage={lead['stage_id']}")
```

### 3. Decide action

Evaluate the duplicates using the merge policy at `docs/kb/20-odoo/05-runbooks/merge-policy.md`.

- **0 or 1 lead found** → No duplicates; stop.
- **2+ leads found** → Identify the *primary* (keep) and *secondary* (merge/archive) records.

### 4a. Archive duplicates (safe, reversible)

```python
secondary_ids = [<ID2>, <ID3>]   # IDs to archive (not the primary)
models.execute_kw(db, uid, password,
    'crm.lead', 'write',
    [secondary_ids], {'active': False})
print(f"Archived leads: {secondary_ids}")
```

### 4b. Use Odoo merge action (recommended, if available)

Odoo CRM provides a native merge via the `crm.merge.opportunity` wizard.  
This is best triggered through the UI or via the `action_merge` server action.  
Via XML-RPC, the safest equivalent is to copy key data to the primary record and archive the secondaries.

---

## Output

| Effect | Description |
|---|---|
| Secondary leads archived | `active = False` on duplicate records |
| Primary lead enriched | Relevant fields updated if secondaries had additional data |

---

## Validation

```python
# Confirm only primary remains active
remaining = models.execute_kw(db, uid, password,
    'crm.lead', 'search_read',
    [[['email_from', '=ilike', email], ['active', '=', True]]],
    {'fields': ['id', 'name', 'type']})
assert len(remaining) <= 1, "Still has active duplicates!"
print("Deduplication complete:", remaining)
```

---

## Errors

| Error | Cause | Fix |
|---|---|---|
| `Access Denied` | User lacks write permission | Require CRM Manager |
| Archived leads missing from search | Default domain excludes `active=False` | Always include `['active', '=', True]` or `['active', 'in', [True, False]]` |

---

## Notes

- Always **present the list of duplicates to the user** before archiving.
- Archiving is reversible; `unlink` is permanent — prefer archiving.
- Check both `email_from` (lead email) and linked `partner_id.email` for full deduplication coverage.
- Use `=ilike` for case-insensitive email matching.
