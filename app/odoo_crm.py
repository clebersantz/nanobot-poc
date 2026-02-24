"""Odoo XML-RPC client — generic low-level tools for the Nanobot AI agent.

The AI agent learns *what* to do from the knowledge file at
``app/knowledge/odoo_crm.md`` and uses these generic primitives to
execute each step.  No business-logic helpers live here; all CRM
reasoning is performed by the LLM.

Environment variables:
    ODOO_URL              Base URL of the Odoo instance (e.g. https://mycompany.odoo.com)
    ODOO_DB               Database name
    ODOO_USERNAME         Odoo user login (e.g. admin)
    ODOO_PASSWORD         Odoo user password or API key
    ODOO_INITIAL_STAGE    Name of the "initial" CRM stage (default: "INITIAL")
    ODOO_IN_PROGRESS_STAGE Name of the "in progress" CRM stage (default: "IN PROGRESS")
"""

import os
import pathlib
import xmlrpc.client

ODOO_URL = os.getenv("ODOO_URL", "")
ODOO_DB = os.getenv("ODOO_DB", "")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "")

NANOBOT_MESSAGE = "Hello, processed by Nanobot"

# Path to the Odoo CRM knowledge file loaded into the agent's system prompt
_KNOWLEDGE_PATH = pathlib.Path(__file__).parent / "knowledge" / "odoo_crm.md"


def load_knowledge() -> str:
    """Return the contents of the Odoo CRM knowledge file."""
    return _KNOWLEDGE_PATH.read_text(encoding="utf-8")


def _validate_config() -> None:
    missing = [v for v in ("ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_PASSWORD") if not os.getenv(v)]
    if missing:
        raise EnvironmentError(f"Missing Odoo configuration variables: {', '.join(missing)}")


def _get_uid() -> int:
    """Authenticate against Odoo and return the user id (uid)."""
    _validate_config()
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
    if not uid:
        raise PermissionError("Odoo authentication failed. Check ODOO_USERNAME and ODOO_PASSWORD.")
    return uid


def _models() -> xmlrpc.client.ServerProxy:
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")


def _execute(models: xmlrpc.client.ServerProxy, uid: int, model: str, method: str, *args, **kwargs):
    return models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, model, method, list(args), kwargs)


# ---------------------------------------------------------------------------
# Generic Odoo tools — the only surface exposed to the AI agent
# ---------------------------------------------------------------------------

def tool_odoo_search(model: str, domain: list, limit: int = 100, offset: int = 0) -> list[int]:
    """Search Odoo records matching *domain* and return a list of IDs.

    Args:
        model:  Odoo model name, e.g. ``"crm.lead"`` or ``"crm.stage"``.
        domain: Odoo domain filter, e.g. ``[["name", "ilike", "INITIAL"]]``.
        limit:  Maximum number of IDs to return (default 100).
        offset: Number of records to skip (default 0).
    """
    uid = _get_uid()
    proxy = _models()
    return _execute(proxy, uid, model, "search", domain, limit=limit, offset=offset)


def tool_odoo_read(model: str, ids: list[int], fields: list[str]) -> list[dict]:
    """Read *fields* from Odoo records identified by *ids*.

    Args:
        model:  Odoo model name.
        ids:    List of record IDs to read.
        fields: List of field names to return.
    """
    uid = _get_uid()
    proxy = _models()
    return _execute(proxy, uid, model, "read", ids, fields=fields)


def tool_odoo_write(model: str, ids: list[int], values: dict) -> bool:
    """Write *values* to Odoo records identified by *ids*.

    Args:
        model:  Odoo model name.
        ids:    List of record IDs to update.
        values: Dict of field → value to write, e.g. ``{"stage_id": 7}``.
    """
    uid = _get_uid()
    proxy = _models()
    return _execute(proxy, uid, model, "write", [ids], values)


def tool_odoo_call(model: str, method: str, args: list, kwargs: dict) -> object:
    """Call any Odoo model method (e.g. ``message_post``, ``action_*``).

    Args:
        model:  Odoo model name.
        method: Method name to call.
        args:   Positional arguments list. The first element is usually a list
                of record IDs, e.g. ``[[101]]``.
        kwargs: Keyword arguments dict, e.g. ``{"body": "...", "message_type": "comment"}``.
    """
    uid = _get_uid()
    proxy = _models()
    return proxy.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, model, method, args, kwargs)


