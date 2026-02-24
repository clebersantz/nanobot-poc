# Process: Change Pipeline Stage

## Purpose

Move a `crm.lead` record to a different pipeline stage by updating `stage_id`.

---

## Inputs

| Parameter | Type | Required | Description |
|---|---|---|---|
| `lead_id` | int | ✓ | ID of the lead/opportunity |
| `stage_name` | string | ✓* | Target stage name (use to resolve ID) |
| `stage_id` | int | ✓* | Target stage ID (if already known) |

*Provide either `stage_name` or `stage_id`.

---

## Steps

### 1. Establish connection

See `docs/kb/20-odoo/01-connection/xmlrpc-connection.md`.

### 2. Resolve available stages

```python
stages = models.execute_kw(db, uid, password,
    'crm.stage', 'search_read',
    [[]], {'fields': ['id', 'name', 'sequence'], 'order': 'sequence'})

print("Available stages:")
for s in stages:
    print(f"  id={s['id']}  name={s['name']!r}")
```

### 3. Find the target stage ID

```python
target_stage_name = '<STAGE_NAME>'  # e.g. 'Qualified', 'Proposition', 'Won'
target_stage = next(
    (s for s in stages if s['name'] == target_stage_name), None)

if not target_stage:
    raise ValueError(f"Stage '{target_stage_name}' not found. Available: {[s['name'] for s in stages]}")

stage_id = target_stage['id']
```

### 4. Move the lead to the new stage

```python
models.execute_kw(db, uid, password,
    'crm.lead', 'write',
    [[<LEAD_ID>]], {'stage_id': stage_id})
print(f"Lead {<LEAD_ID>} moved to stage '{target_stage_name}' (id={stage_id})")
```

---

## Output

| Value | Type | Description |
|---|---|---|
| `True` | bool | Stage change succeeded |

---

## Validation

```python
lead = models.execute_kw(db, uid, password,
    'crm.lead', 'read', [[<LEAD_ID>]],
    {'fields': ['name', 'stage_id']})
print(lead)  # stage_id should be [<stage_id>, '<STAGE_NAME>']
```

---

## Errors

| Error | Cause | Fix |
|---|---|---|
| Stage not found | Stage name typo or non-existent | List all stages and verify name |
| `Access Denied` | User lacks CRM write permission | Check user CRM group |
| Stage belongs to different team | Stage filtered by `team_id` | Check stage's `team_id` field |

---

## Notes

- Stage IDs are **instance-specific** — never hard-code them.
- The `Won` and `Lost` states in Odoo CRM are not necessarily distinct stages; mark won/lost using the `action_set_won` / `action_set_lost` methods for proper pipeline tracking.
- Changing stage does not automatically change `probability` unless the stage has a configured probability.
