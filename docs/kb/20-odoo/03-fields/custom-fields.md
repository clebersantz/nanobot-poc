# Custom Fields on crm.lead

## Purpose

Odoo instances often have custom fields added via Studio, development, or OCA modules. This document explains how to discover and use them via XML-RPC.

---

## Discovering Custom Fields

Custom fields typically have names prefixed with `x_` (Studio) or a module prefix.

```python
# Fetch all fields and filter for custom ones
fields_meta = models.execute_kw(db, uid, password,
    'crm.lead', 'fields_get', [],
    {'attributes': ['string', 'type', 'required', 'help']})

custom_fields = {k: v for k, v in fields_meta.items() if k.startswith('x_')}
for fname, fmeta in sorted(custom_fields.items()):
    print(f"{fname:40s} {fmeta['type']:15s} {fmeta.get('string','')}")
```

---

## Reading Custom Field Values

```python
leads = models.execute_kw(db, uid, password,
    'crm.lead', 'search_read',
    [[['id', '=', <LEAD_ID>]]],
    {'fields': ['name', 'x_<CUSTOM_FIELD_NAME>']})
```

Replace `x_<CUSTOM_FIELD_NAME>` with the actual technical field name discovered above.

---

## Writing Custom Field Values

```python
models.execute_kw(db, uid, password,
    'crm.lead', 'write',
    [[<LEAD_ID>]],
    {'x_<CUSTOM_FIELD_NAME>': '<VALUE>'})
```

---

## Custom Field Types and Value Formats

| Odoo Type | Python Value Format | Example |
|---|---|---|
| `char` | string | `"Acme Corp"` |
| `integer` | int | `42` |
| `float` | float | `9.99` |
| `boolean` | bool | `True` / `False` |
| `date` | string `YYYY-MM-DD` | `"2025-12-31"` |
| `datetime` | string `YYYY-MM-DD HH:MM:SS` | `"2025-12-31 09:00:00"` |
| `selection` | string (key) | `"done"` |
| `many2one` | int (ID) | `5` |
| `many2many` | `[[6, 0, [id1, id2]]]` | `[[6, 0, [3, 7]]]` |
| `one2many` | `[[0, 0, {...}]]` (create) | varies |

---

## Placeholder Notice

> Custom fields are **instance-specific**. The field names in this document use the placeholder `x_<CUSTOM_FIELD_NAME>`. Always run the discovery query above to get actual field names for the target Odoo instance before using them in any automation.

---

## Notes

- Fields created with Odoo Studio are prefixed `x_studio_`.
- OCA module fields typically use a module-specific prefix (e.g., `crm_<module>_<field>`).
- Custom `selection` fields require you to read the allowed values from `fields_get` before writing:
  ```python
  selection_values = fields_meta['x_<FIELD>']['selection']
  # Returns list of [key, label] pairs
  ```
