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


# ---------------------------------------------------------------------------
# OpenAI tool-callable functions
# These are standalone wrappers used by the AI agent loop in the webhook.
# Each function authenticates independently so they can be called by the LLM.
# ---------------------------------------------------------------------------

def tool_get_lead_info(lead_id: int) -> dict:
    """Return details of a single CRM lead including its current stage name."""
    uid = _get_uid()
    models = _models_proxy()
    records = _execute(
        models, uid, "crm.lead", "read",
        [lead_id],
        fields=["id", "name", "stage_id", "description", "partner_id", "user_id"],
    )
    if not records:
        return {"error": f"Lead {lead_id} not found."}
    rec = records[0]
    # stage_id is returned as [id, name] by Odoo
    rec["stage_name"] = rec["stage_id"][1] if isinstance(rec["stage_id"], list) else str(rec["stage_id"])
    return rec


def tool_list_crm_stages() -> list[dict]:
    """Return all available CRM pipeline stages (id and name)."""
    uid = _get_uid()
    models = _models_proxy()
    stage_ids = _execute(models, uid, "crm.stage", "search", [[]])
    if not stage_ids:
        return []
    stages = _execute(models, uid, "crm.stage", "read", stage_ids, fields=["id", "name", "sequence"])
    return stages


def tool_post_message_on_lead(lead_id: int, message: str) -> dict:
    """Post a chatter note on a CRM lead and return a confirmation."""
    uid = _get_uid()
    models = _models_proxy()
    post_message_on_lead(models, uid, lead_id, message)
    return {"lead_id": lead_id, "message_posted": message}


def tool_move_lead_to_stage_by_name(lead_id: int, stage_name: str) -> dict:
    """Move a CRM lead to the stage identified by *stage_name* and return a confirmation."""
    uid = _get_uid()
    models = _models_proxy()
    stage_id = get_stage_id(models, uid, stage_name)
    move_lead_to_stage(models, uid, lead_id, stage_id)
    return {"lead_id": lead_id, "moved_to_stage": stage_name}


# ---------------------------------------------------------------------------
# Batch helper (non-AI path)
# ---------------------------------------------------------------------------

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

