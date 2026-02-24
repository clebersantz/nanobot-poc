# crm.lead — Field Reference

Comprehensive field reference for the `crm.lead` model in Odoo 18.

---

## Core Identity Fields

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | integer | auto | Primary key |
| `name` | char | ✓ | Title of the lead/opportunity |
| `type` | selection | ✓ | `'lead'` or `'opportunity'` |
| `active` | boolean | — | Archived if `False` (default `True`) |
| `company_id` | many2one | — | Owning Odoo company |

## Contact Fields

| Field | Type | Description |
|---|---|---|
| `partner_id` | many2one → `res.partner` | Linked existing customer |
| `partner_name` | char | Company name (when no partner linked) |
| `contact_name` | char | Contact person name |
| `email_from` | char | Primary email |
| `phone` | char | Phone number |
| `mobile` | char | Mobile number |
| `website` | char | Website URL |
| `street` | char | Address line 1 |
| `street2` | char | Address line 2 |
| `city` | char | City |
| `state_id` | many2one → `res.country.state` | State / Province |
| `zip` | char | Postal/ZIP code |
| `country_id` | many2one → `res.country` | Country |

## Pipeline Fields

| Field | Type | Description |
|---|---|---|
| `stage_id` | many2one → `crm.stage` | Current pipeline stage |
| `user_id` | many2one → `res.users` | Assigned salesperson |
| `team_id` | many2one → `crm.team` | Sales team |
| `priority` | selection | `'0'` Normal · `'1'` Low · `'2'` High · `'3'` Very High |
| `kanban_state` | selection | `'normal'` · `'done'` · `'blocked'` |
| `probability` | float | Win probability 0–100 |
| `automated_probability` | float | AI-predicted probability (read-only) |
| `expected_revenue` | float | Forecast value |
| `prorated_revenue` | float | `probability/100 × expected_revenue` (computed) |
| `date_deadline` | date | Expected close date |
| `date_open` | datetime | Conversion to opportunity date |
| `date_closed` | datetime | Won/lost date |
| `date_last_stage_update` | datetime | Last stage change date |

## Classification Fields

| Field | Type | Description |
|---|---|---|
| `tag_ids` | many2many → `crm.tag` | CRM tags |
| `lost_reason_id` | many2one → `crm.lost.reason` | Reason if lost |
| `referred` | char | Referral source (free text) |
| `source_id` | many2one → `utm.source` | UTM source |
| `medium_id` | many2one → `utm.medium` | UTM medium |
| `campaign_id` | many2one → `utm.campaign` | UTM campaign |

## Activity / Communication Fields

| Field | Type | Description |
|---|---|---|
| `activity_ids` | one2many → `mail.activity` | Scheduled activities |
| `activity_state` | selection | `'overdue'`, `'today'`, `'planned'`, `False` (computed) |
| `message_ids` | one2many → `mail.message` | Chatter messages |
| `description` | html | Internal notes |

---

## Discovering All Fields via XML-RPC

```python
# Get all field metadata for crm.lead
fields_meta = models.execute_kw(db, uid, password,
    'crm.lead', 'fields_get', [],
    {'attributes': ['string', 'type', 'required', 'readonly', 'help']})

for fname, fmeta in sorted(fields_meta.items()):
    print(f"{fname:40s} {fmeta['type']:15s} {fmeta.get('string','')}")
```

---

## Stage ID Lookup

```python
stages = models.execute_kw(db, uid, password,
    'crm.stage', 'search_read',
    [[]], {'fields': ['id', 'name', 'sequence'], 'order': 'sequence'})
# Use returned IDs when setting stage_id — never assume fixed values
```
