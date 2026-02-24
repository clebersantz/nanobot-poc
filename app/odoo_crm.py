"""Odoo CRM integration via XML-RPC.

Environment variables:
    ODOO_URL              Base URL of the Odoo instance (e.g. https://mycompany.odoo.com)
    ODOO_DB               Database name
    ODOO_USERNAME         Odoo user login (e.g. admin)
    ODOO_PASSWORD         Odoo user password or API key
    ODOO_INITIAL_STAGE    Name of the "initial" CRM stage (default: "INITIAL")
    ODOO_IN_PROGRESS_STAGE Name of the "in progress" CRM stage (default: "IN PROGRESS")
"""

import os
import xmlrpc.client

ODOO_URL = os.getenv("ODOO_URL", "")
ODOO_DB = os.getenv("ODOO_DB", "")
ODOO_USERNAME = os.getenv("ODOO_USERNAME", "")
ODOO_PASSWORD = os.getenv("ODOO_PASSWORD", "")
ODOO_INITIAL_STAGE = os.getenv("ODOO_INITIAL_STAGE", "INITIAL")
ODOO_IN_PROGRESS_STAGE = os.getenv("ODOO_IN_PROGRESS_STAGE", "IN PROGRESS")

NANOBOT_MESSAGE = "Hello, processed by Nanobot"


def _validate_config() -> None:
    missing = [v for v in ("ODOO_URL", "ODOO_DB", "ODOO_USERNAME", "ODOO_PASSWORD") if not os.getenv(v)]
    if missing:
        raise EnvironmentError(f"Missing Odoo configuration variables: {', '.join(missing)}")


def _get_uid() -> int:
    """Authenticate and return the user id (uid)."""
    _validate_config()
    common = xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common")
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
    if not uid:
        raise PermissionError("Odoo authentication failed. Check ODOO_USERNAME and ODOO_PASSWORD.")
    return uid


def _models_proxy() -> xmlrpc.client.ServerProxy:
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object")


def _execute(models: xmlrpc.client.ServerProxy, uid: int, model: str, method: str, *args, **kwargs):
    return models.execute_kw(ODOO_DB, uid, ODOO_PASSWORD, model, method, list(args), kwargs)


def get_stage_id(models: xmlrpc.client.ServerProxy, uid: int, stage_name: str) -> int:
    """Return the id of the CRM stage matching *stage_name* (case-insensitive)."""
    stage_ids = _execute(
        models, uid, "crm.stage", "search",
        [["name", "ilike", stage_name]],
        limit=1,
    )
    if not stage_ids:
        raise ValueError(f"CRM stage '{stage_name}' not found in Odoo.")
    return stage_ids[0]


def get_initial_leads(models: xmlrpc.client.ServerProxy, uid: int) -> list[dict]:
    """Return all leads/opportunities currently in the INITIAL stage."""
    initial_stage_id = get_stage_id(models, uid, ODOO_INITIAL_STAGE)
    lead_ids = _execute(
        models, uid, "crm.lead", "search",
        [["stage_id", "=", initial_stage_id]],
    )
    if not lead_ids:
        return []
    leads = _execute(
        models, uid, "crm.lead", "read",
        lead_ids,
        fields=["id", "name", "stage_id"],
    )
    return leads


def post_message_on_lead(models: xmlrpc.client.ServerProxy, uid: int, lead_id: int, body: str) -> None:
    """Post a chatter message on the given lead."""
    _execute(
        models, uid, "crm.lead", "message_post",
        [lead_id],
        body=body,
        message_type="comment",
        subtype_xmlid="mail.mt_note",
    )


def move_lead_to_stage(models: xmlrpc.client.ServerProxy, uid: int, lead_id: int, stage_id: int) -> None:
    """Move the lead to the given stage id."""
    _execute(
        models, uid, "crm.lead", "write",
        [[lead_id]],
        {"stage_id": stage_id},
    )


def process_lead(lead_id: int) -> dict:
    """Post the nanobot message and move lead to IN PROGRESS.

    Returns a dict with the result for the processed lead.
    Raises ValueError if the lead does not exist in Odoo.
    """
    uid = _get_uid()
    models = _models_proxy()
    # Verify the lead exists
    existing = _execute(models, uid, "crm.lead", "search", [["id", "=", lead_id]], limit=1)
    if not existing:
        raise ValueError(f"Lead with id {lead_id} not found in Odoo.")
    in_progress_stage_id = get_stage_id(models, uid, ODOO_IN_PROGRESS_STAGE)
    post_message_on_lead(models, uid, lead_id, NANOBOT_MESSAGE)
    move_lead_to_stage(models, uid, lead_id, in_progress_stage_id)
    return {"lead_id": lead_id, "status": "processed"}


def process_all_initial_leads() -> list[dict]:
    """Process every lead currently in the INITIAL stage.

    For each lead:
    1. Post 'Hello, processed by Nanobot' as a chatter note.
    2. Move the lead to the IN PROGRESS stage.

    Returns a list of result dicts.
    """
    uid = _get_uid()
    models = _models_proxy()
    leads = get_initial_leads(models, uid)
    if not leads:
        return []
    # Fetch stage id once to avoid repeated lookups
    in_progress_stage_id = get_stage_id(models, uid, ODOO_IN_PROGRESS_STAGE)
    results = []
    for lead in leads:
        lead_id = lead["id"]
        post_message_on_lead(models, uid, lead_id, NANOBOT_MESSAGE)
        move_lead_to_stage(models, uid, lead_id, in_progress_stage_id)
        results.append({"lead_id": lead_id, "name": lead.get("name"), "status": "processed"})
    return results
