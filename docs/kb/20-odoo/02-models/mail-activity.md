# Model: mail.activity

## Purpose

`mail.activity` stores scheduled activities (tasks, calls, meetings, emails) linked to any Odoo record, including `crm.lead`. Agents create activities to prompt salespeople to take action.

---

## Key Fields

| Field | Type | Description |
|---|---|---|
| `id` | integer | Primary key |
| `res_model` | char | Technical model name the activity belongs to, e.g. `'crm.lead'` |
| `res_model_id` | many2one → `ir.model` | Same as `res_model` but as a relation |
| `res_id` | integer | ID of the linked record (e.g. lead ID) |
| `activity_type_id` | many2one → `mail.activity.type` | Type of activity (Email, Call, Meeting, etc.) |
| `summary` | char | Short description shown on the activity card |
| `note` | html | Detailed note / instructions |
| `date_deadline` | date | Due date (required) |
| `user_id` | many2one → `res.users` | Responsible user |
| `state` | selection | `'overdue'`, `'today'`, `'planned'` (computed from deadline) |

---

## Resolving Activity Type IDs

Activity type IDs are instance-specific. Resolve before use:

```python
types = models.execute_kw(db, uid, password,
    'mail.activity.type', 'search_read',
    [[]], {'fields': ['id', 'name']})
# e.g. [{'id': 1, 'name': 'Email'}, {'id': 2, 'name': 'Phone Call'}, ...]
```

---

## Common Operations

### Schedule an activity on a lead

```python
activity_id = models.execute_kw(db, uid, password,
    'mail.activity', 'create', [{
        'res_model': 'crm.lead',
        'res_id': <LEAD_ID>,
        'activity_type_id': <ACTIVITY_TYPE_ID>,  # verify first
        'summary': '<SHORT_DESCRIPTION>',
        'note': '<DETAILED_NOTE>',
        'date_deadline': '<YYYY-MM-DD>',
        'user_id': <USER_ID>,
    }])
```

### List activities for a lead

```python
activities = models.execute_kw(db, uid, password,
    'mail.activity', 'search_read',
    [[['res_model', '=', 'crm.lead'], ['res_id', '=', <LEAD_ID>]]],
    {'fields': ['id', 'activity_type_id', 'summary', 'date_deadline', 'user_id', 'state']})
```

### Mark activity as done

```python
models.execute_kw(db, uid, password,
    'mail.activity', 'action_done', [[<ACTIVITY_ID>]])
```

---

## Notes

- The `state` field is computed and cannot be set directly.
- Creating an activity also posts a message to the record's chatter.
- `date_deadline` must be in `'YYYY-MM-DD'` string format.
- Each record can have multiple concurrent activities.
