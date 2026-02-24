# Runbook: Merge Policy for Duplicate Leads

## Purpose

Define which record to keep (primary) and which to archive (secondary) when duplicate leads are found, and how to consolidate data before archiving.

---

## Decision Criteria

Apply the following rules in order to select the **primary** (keep) record:

| Priority | Rule |
|---|---|
| 1 | Prefer records of type `'opportunity'` over `'lead'` |
| 2 | Prefer records with a `partner_id` set |
| 3 | Prefer records with the higher `probability` |
| 4 | Prefer the record with the most recent `date_last_stage_update` |
| 5 | If still tied, prefer the record with the lowest `id` (oldest) |

---

## Data Consolidation Before Archiving

Before archiving secondary records, check and copy any unique data to the primary:

```python
primary_id   = <PRIMARY_LEAD_ID>
secondary_id = <SECONDARY_LEAD_ID>

primary   = models.execute_kw(db, uid, password,
    'crm.lead', 'read', [[primary_id]],
    {'fields': ['name', 'description', 'phone', 'mobile',
                'expected_revenue', 'tag_ids']})[0]

secondary = models.execute_kw(db, uid, password,
    'crm.lead', 'read', [[secondary_id]],
    {'fields': ['name', 'description', 'phone', 'mobile',
                'expected_revenue', 'tag_ids']})[0]

updates = {}

# Copy phone/mobile if missing on primary
if not primary['phone'] and secondary['phone']:
    updates['phone'] = secondary['phone']

if not primary['mobile'] and secondary['mobile']:
    updates['mobile'] = secondary['mobile']

# Use higher expected revenue
if secondary['expected_revenue'] > primary['expected_revenue']:
    updates['expected_revenue'] = secondary['expected_revenue']

# Merge description (append)
if secondary['description']:
    combined = (primary['description'] or '') + \
               '\n\n--- Merged from lead #' + str(secondary_id) + ' ---\n\n' + \
               secondary['description']
    updates['description'] = combined

# Merge tags
if secondary['tag_ids']:
    merged_tags = list(set(primary['tag_ids'] + secondary['tag_ids']))
    updates['tag_ids'] = [[6, 0, merged_tags]]

if updates:
    models.execute_kw(db, uid, password,
        'crm.lead', 'write', [[primary_id]], updates)
    print(f"Primary {primary_id} updated with: {list(updates.keys())}")
```

---

## Archiving the Secondary

```python
models.execute_kw(db, uid, password,
    'crm.lead', 'write',
    [[secondary_id]], {'active': False})
print(f"Secondary lead {secondary_id} archived.")
```

---

## Output

| Effect | Description |
|---|---|
| Primary enriched | Missing data copied from secondary |
| Secondary archived | `active = False`, remains recoverable |

---

## Validation

```python
primary_check = models.execute_kw(db, uid, password,
    'crm.lead', 'read', [[primary_id]],
    {'fields': ['name', 'phone', 'mobile', 'expected_revenue', 'active']})
print("Primary after merge:", primary_check)

secondary_check = models.execute_kw(db, uid, password,
    'crm.lead', 'read', [[secondary_id]],
    {'fields': ['active']})
assert not secondary_check[0]['active'], "Secondary not archived!"
```

---

## Notes

- Always log the merge decision and which fields were copied.
- Never use `unlink` during a merge — archiving preserves audit trail.
- If there are open activities on the secondary, reassign them to the primary before archiving:
  ```python
  models.execute_kw(db, uid, password,
      'mail.activity', 'write',
      [[<ACTIVITY_IDS>]], {'res_id': primary_id})
  ```
- Review the merged record in Odoo UI to confirm correctness.
