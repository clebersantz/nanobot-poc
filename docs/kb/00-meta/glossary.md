# Glossary

Key terms used throughout this knowledge base.

---

| Term | Definition |
|---|---|
| **CRM Lead** | A prospective customer record in Odoo (`crm.lead` model). Can be a *lead* (unqualified) or an *opportunity* (qualified). |
| **Opportunity** | A `crm.lead` record where `type = 'opportunity'`. Has a sales pipeline stage and expected revenue. |
| **Stage** | A pipeline step represented by `crm.stage`. Identified by `id` (integer) or `name` (string). Verify IDs via XML-RPC before use. |
| **XML-RPC** | Remote Procedure Call protocol over HTTP/XML used by Odoo's external API (`/xmlrpc/2/common` and `/xmlrpc/2/object`). |
| **execute_kw** | The primary XML-RPC method on the `object` endpoint used to call any Odoo model method (e.g., `search`, `read`, `create`, `write`, `unlink`). |
| **uid** | User ID (integer) returned by `authenticate`. Required for all `execute_kw` calls. |
| **Partner** | A company or individual in `res.partner`. Linked to leads via `partner_id`. |
| **Salesperson** | An Odoo user (`res.users`) assigned to a lead via `user_id`. |
| **Activity** | A scheduled task on a record (`mail.activity`). Types defined in `mail.activity.type`. |
| **Activity Type** | Category of an activity (e.g., "Email", "Phone Call", "Meeting"). Stored in `mail.activity.type`. Verify IDs via XML-RPC. |
| **Probability** | Estimated win probability (0–100) of an opportunity, stored as a float in `crm.lead.probability`. |
| **Expected Revenue** | Forecasted deal value stored in `crm.lead.expected_revenue` (float). |
| **Kanban State** | Visual indicator (`normal`, `done`, `blocked`) for quick status on pipeline cards. Field: `kanban_state`. |
| **Domain** | Odoo filter expression — a list of triples `[field, operator, value]`, e.g., `[['email_from', '=', 'a@b.com']]`. |
| **Context** | Optional dict passed to `execute_kw` to influence behaviour (e.g., language, timezone). |
| **Nanobot** | The AI agent framework (nanobot.ai) that indexes this knowledge base to answer questions and automate tasks. |
| **Chunk** | A text segment produced when a document is split for indexing into a vector store. |
| **Top-K** | Number of most-relevant chunks retrieved from the vector store to form the LLM context. |
| **Placeholder** | Value marked with `<ANGLE_BRACKETS>` that must be replaced with an instance-specific real value before execution. |
