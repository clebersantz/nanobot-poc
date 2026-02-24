# Process: Assign Owner (Salesperson) to a Lead

## Purpose

Set or change the salesperson (`user_id`) assigned to a `crm.lead` record.

---

## Inputs

| Parameter | Type | Required | Description |
|---|---|---|---|
| `lead_id` | int | ✓ | ID of the lead |
| `user_email` | string | ✓* | Login/email of the target salesperson |
| `user_id` | int | ✓* | User ID of the target salesperson (if known) |

*Provide either `user_email` or `user_id`.

---

## Steps

### 1. Establish connection

See `docs/kb/20-odoo/01-connection/xmlrpc-connection.md`.

### 2. Resolve the user ID from email/login

```python
users = models.execute_kw(db, uid, password,
    'res.users', 'search_read',
    [[['login', '=', '<SALESPERSON_EMAIL>'], ['active', '=', True]]],
    {'fields': ['id', 'name', 'login']})

if not users:
    raise ValueError(f"User '<SALESPERSON_EMAIL>' not found in Odoo.")

target_user = users[0]
print(f"Assigning to: {target_user['name']} (id={target_user['id']})")
```

### 3. Assign the salesperson

```python
models.execute_kw(db, uid, password,
    'crm.lead', 'write',
    [[<LEAD_ID>]], {'user_id': target_user['id']})
print(f"Lead {<LEAD_ID>} assigned to {target_user['name']}")
```

### (Optional) Also assign to a sales team

```python
# Resolve team ID first
teams = models.execute_kw(db, uid, password,
    'crm.team', 'search_read',
    [[['name', '=', '<TEAM_NAME>']]], {'fields': ['id', 'name']})
team_id = teams[0]['id'] if teams else None

models.execute_kw(db, uid, password,
    'crm.lead', 'write',
    [[<LEAD_ID>]], {
        'user_id': target_user['id'],
        'team_id': team_id,
    })
```

---

## Output

| Value | Type | Description |
|---|---|---|
| `True` | bool | Assignment succeeded |

---

## Validation

```python
lead = models.execute_kw(db, uid, password,
    'crm.lead', 'read', [[<LEAD_ID>]],
    {'fields': ['name', 'user_id', 'team_id']})
print(lead)
# user_id should be [<user_id>, '<SALESPERSON_NAME>']
```

---

## Errors

| Error | Cause | Fix |
|---|---|---|
| User not found | Wrong email or inactive user | Check `active = True` and correct login |
| `Access Denied` | Caller lacks CRM write rights | Ensure caller is CRM Manager or above |
| Portal user assigned | Target user is a portal/shared user | Only internal users can be salespersons |
