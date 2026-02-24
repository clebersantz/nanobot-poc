# Model: res.partner

## Purpose

`res.partner` stores contacts — companies and individuals. Leads can be linked to a partner via `crm.lead.partner_id`. When converting a lead to an opportunity, Odoo can create or link a partner automatically.

---

## Key Fields

| Field | Type | Description |
|---|---|---|
| `id` | integer | Primary key |
| `name` | char | Full name or company name (required) |
| `is_company` | boolean | `True` if the record is a company |
| `company_id` | many2one → `res.partner` | Parent company (for contacts) |
| `email` | char | Primary email address |
| `phone` | char | Phone number |
| `mobile` | char | Mobile number |
| `street` | char | Street address |
| `city` | char | City |
| `state_id` | many2one → `res.country.state` | State/Province |
| `country_id` | many2one → `res.country` | Country |
| `zip` | char | Postal/ZIP code |
| `vat` | char | Tax ID / VAT number |
| `active` | boolean | `False` if archived |

---

## Common Operations

### Search partner by email

```python
partners = models.execute_kw(db, uid, password,
    'res.partner', 'search_read',
    [[['email', '=', '<EMAIL_ADDRESS>']]],
    {'fields': ['id', 'name', 'email', 'phone', 'is_company']})
```

### Create a new partner

```python
partner_id = models.execute_kw(db, uid, password,
    'res.partner', 'create', [{
        'name': '<FULL_NAME>',
        'email': '<EMAIL_ADDRESS>',
        'phone': '<PHONE>',
        'is_company': False,
    }])
```

### Link a partner to a lead

```python
models.execute_kw(db, uid, password,
    'crm.lead', 'write',
    [[<LEAD_ID>]], {'partner_id': partner_id})
```

---

## Notes

- Partners are shared across all Odoo modules (Sales, CRM, Accounting, etc.).
- Duplicate partners (same email) can cause issues; check before creating.
- `is_company = True` + `company_id = False` → root company record.
- Individual contacts should have `company_id` set to their parent company.
