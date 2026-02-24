# Model: crm.lead

## Purpose

`crm.lead` is the central model for both **leads** (unqualified prospects) and **opportunities** (qualified prospects in the sales pipeline). Understanding this model is essential for all CRM automation tasks.

---

## Key Fields

| Field | Type | Description |
|---|---|---|
| `id` | integer | Auto-generated primary key |
| `name` | char | Lead/opportunity title (required) |
| `type` | selection | `'lead'` or `'opportunity'` |
| `stage_id` | many2one → `crm.stage` | Current pipeline stage |
| `user_id` | many2one → `res.users` | Assigned salesperson |
| `team_id` | many2one → `crm.team` | Sales team |
| `partner_id` | many2one → `res.partner` | Linked customer/company |
| `contact_name` | char | Contact person name (if no partner) |
| `email_from` | char | Contact email address |
| `phone` | char | Contact phone number |
| `mobile` | char | Contact mobile number |
| `partner_name` | char | Company name (unlinked lead) |
| `description` | html | Internal notes |
| `probability` | float | Win probability (0–100) |
| `expected_revenue` | float | Forecasted deal value |
| `priority` | selection | `'0'` (Normal), `'1'` (Low), `'2'` (High), `'3'` (Very High) |
| `kanban_state` | selection | `'normal'`, `'done'`, `'blocked'` |
| `date_deadline` | date | Expected closing date |
| `date_open` | datetime | Date converted to opportunity |
| `date_closed` | datetime | Date marked won/lost |
| `active` | boolean | `False` if archived |
| `lost_reason_id` | many2one → `crm.lost.reason` | Reason for marking lost |
| `tag_ids` | many2many → `crm.tag` | CRM tags |
| `company_id` | many2one → `res.company` | Owning company |

> For a full field list, run:
> ```python
> fields = models.execute_kw(db, uid, password,
>     'crm.lead', 'fields_get', [],
>     {'attributes': ['string', 'type', 'required']})
> ```

---

## Common Operations

### Search open opportunities

```python
leads = models.execute_kw(db, uid, password,
    'crm.lead', 'search_read',
    [[['type', '=', 'opportunity'], ['active', '=', True]]],
    {'fields': ['id', 'name', 'stage_id', 'user_id', 'probability'],
     'limit': 50})
```

### Read a single lead

```python
lead = models.execute_kw(db, uid, password,
    'crm.lead', 'read',
    [[<LEAD_ID>]],
    {'fields': ['name', 'email_from', 'stage_id', 'probability']})
```

---

## Notes

- Converting a lead to an opportunity sets `type = 'opportunity'` and assigns a `stage_id`.
- Archiving a lead sets `active = False`; use `[['active', '=', False]]` to find archived records.
- Stage IDs are instance-specific. Always resolve them with `crm.stage` `search_read` before use.
