# Process: Schedule Next Activity on a Lead

## Purpose

Create a `mail.activity` record on a `crm.lead` to remind the salesperson of a follow-up action (call, email, meeting, etc.).

---

## Inputs

| Parameter | Type | Required | Description |
|---|---|---|---|
| `lead_id` | int | ✓ | ID of the lead |
| `activity_type_name` | string | ✓* | Name of the activity type (e.g. `'Phone Call'`) |
| `activity_type_id` | int | ✓* | Activity type ID (if already known) |
| `summary` | string | — | Short description (shown on Kanban card) |
| `note` | string | — | Detailed instructions (HTML allowed) |
| `date_deadline` | string | ✓ | Due date as `'YYYY-MM-DD'` |
| `user_id` | int | — | Responsible user (defaults to current user) |

*Provide either `activity_type_name` or `activity_type_id`.

---

## Steps

### 1. Establish connection

See `docs/kb/20-odoo/01-connection/xmlrpc-connection.md`.

### 2. Resolve activity type ID

```python
act_types = models.execute_kw(db, uid, password,
    'mail.activity.type', 'search_read',
    [[]], {'fields': ['id', 'name']})

print("Available activity types:")
for t in act_types:
    print(f"  id={t['id']}  name={t['name']!r}")

target_type_name = '<ACTIVITY_TYPE_NAME>'  # e.g. 'Phone Call', 'Email', 'Meeting'
act_type = next((t for t in act_types if t['name'] == target_type_name), None)

if not act_type:
    raise ValueError(f"Activity type '{target_type_name}' not found.")

activity_type_id = act_type['id']
```

### 3. Compute deadline date

```python
from datetime import date, timedelta

# Example: schedule for 3 days from today
deadline = (date.today() + timedelta(days=3)).strftime('%Y-%m-%d')
# Or use a fixed date: deadline = '<YYYY-MM-DD>'
```

### 4. Create the activity

```python
activity_id = models.execute_kw(db, uid, password,
    'mail.activity', 'create', [{
        'res_model': 'crm.lead',
        'res_id': <LEAD_ID>,
        'activity_type_id': activity_type_id,
        'summary': '<SHORT_SUMMARY>',
        'note': '<DETAILED_NOTE>',
        'date_deadline': deadline,
        'user_id': <RESPONSIBLE_USER_ID>,  # omit to use current uid
    }])
print(f"Activity created with ID: {activity_id}")
```

---

## Output

| Variable | Type | Description |
|---|---|---|
| `activity_id` | int | ID of the created activity |

---

## Validation

```python
activity = models.execute_kw(db, uid, password,
    'mail.activity', 'read', [[activity_id]],
    {'fields': ['activity_type_id', 'summary', 'date_deadline', 'user_id', 'state']})
print(activity)
```

---

## Errors

| Error | Cause | Fix |
|---|---|---|
| Activity type not found | Wrong name or not installed | List all types and verify |
| `date_deadline` format error | Wrong date format | Use `'YYYY-MM-DD'` string |
| `Access Denied` | User lacks activity creation rights | Ensure CRM User access |
| Lead not found | Wrong `lead_id` | Verify with `search_read` |
