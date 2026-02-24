# Model: res.users

## Purpose

`res.users` represents Odoo system users (salespersons, managers, admins). Leads are assigned to users via `crm.lead.user_id`. Activities are also assigned to users.

---

## Key Fields

| Field | Type | Description |
|---|---|---|
| `id` | integer | Primary key (= `uid` after authentication) |
| `name` | char | Display name |
| `login` | char | Login email/username |
| `email` | char | Email address |
| `active` | boolean | `False` if the user is archived |
| `groups_id` | many2many → `res.groups` | Security groups the user belongs to |
| `partner_id` | many2one → `res.partner` | Linked partner record |
| `share` | boolean | `True` for portal/public users |
| `company_id` | many2one → `res.company` | Primary company |

---

## Common Operations

### List all internal (non-portal) users

```python
users = models.execute_kw(db, uid, password,
    'res.users', 'search_read',
    [[['active', '=', True], ['share', '=', False]]],
    {'fields': ['id', 'name', 'login', 'email']})
```

### Find a user by email/login

```python
users = models.execute_kw(db, uid, password,
    'res.users', 'search_read',
    [[['login', '=', '<EMAIL_OR_LOGIN>']]],
    {'fields': ['id', 'name', 'login']})
```

### Get the currently authenticated user

```python
me = models.execute_kw(db, uid, password,
    'res.users', 'read', [[uid]],
    {'fields': ['id', 'name', 'login', 'company_id']})
```

---

## Notes

- **Never** call `write` on `res.users` unless explicitly changing user settings — use dedicated Odoo actions instead.
- Portal users (`share = True`) cannot be assigned as salespersons.
- The `uid` from `authenticate` is the `res.users.id` of the authenticated user.
- In a multi-company setup, a user may belong to multiple companies via `company_ids`.
