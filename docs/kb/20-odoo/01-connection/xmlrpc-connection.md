# XML-RPC Connection to Odoo 18

## Purpose

Establish an authenticated XML-RPC session to an Odoo 18 instance so that subsequent `execute_kw` calls can read and write records.

---

## Inputs

| Parameter | Type | Description |
|---|---|---|
| `<ODOO_URL>` | string | Base URL of the Odoo instance, e.g. `https://mycompany.odoo.com` |
| `<DB_NAME>` | string | Database name (visible in the Odoo login screen) |
| `<USERNAME>` | string | Odoo login (usually an email address) |
| `<PASSWORD>` | string | Odoo password or API key (preferred) |

> **Security:** Use an **API key** instead of a plain password whenever possible.  
> Generate one in Odoo → Settings → My Profile → API Keys.

---

## Steps

### 1. Import libraries and define connection parameters

```python
import xmlrpc.client

url      = "<ODOO_URL>"          # e.g. "https://mycompany.odoo.com"
db       = "<DB_NAME>"
username = "<USERNAME>"
password = "<PASSWORD>"          # or API key
```

### 2. Create the two XML-RPC endpoints

```python
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")
```

### 3. Verify server version (optional but recommended)

```python
version_info = common.version()
print(version_info)
# Expected: {'server_version': '18.0', 'server_version_info': [18, 0, 0, 'final', 0, ''], ...}
```

### 4. Authenticate and obtain UID

```python
uid = common.authenticate(db, username, password, {})
if not uid:
    raise RuntimeError("Authentication failed – check URL, DB name, username, and password/API key.")
print(f"Authenticated as UID {uid}")
```

---

## Output

| Variable | Type | Description |
|---|---|---|
| `uid` | int | Numeric user ID; required for all `execute_kw` calls |
| `models` | ServerProxy | Proxy object for calling model methods |

---

## Validation

```python
# Confirm access by reading your own user record
me = models.execute_kw(db, uid, password,
    'res.users', 'read', [[uid]], {'fields': ['name', 'login']})
print(me)  # [{'id': <uid>, 'name': '...', 'login': '...'}]
```

---

## Errors

| Symptom | Likely Cause | Fix |
|---|---|---|
| `uid` is `False` | Wrong credentials or DB name | Double-check URL, DB, username, password |
| `ConnectionRefusedError` | Wrong URL or port | Verify `<ODOO_URL>` is reachable |
| `ProtocolError: 404` | Wrong endpoint path | Ensure `/xmlrpc/2/common` path is correct |
| `xmlrpc.client.Fault: Access Denied` | User lacks permission | Check user roles/groups in Odoo |

---

## Notes

- Odoo 18 Community and Enterprise both expose `/xmlrpc/2/common` and `/xmlrpc/2/object`.
- `ServerProxy` objects are **not thread-safe** — create one per thread or use a connection pool.
- For HTTPS with self-signed certificates, pass `context=ssl._create_unverified_context()` to `ServerProxy` (not recommended for production).
