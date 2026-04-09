# Odoo Module Implementation Plan - jinstage_helpdesk_repair

## Task Overview

Module development based on Odoo 17.0 Enterprise framework. This module extends `helpdesk` into a
full Repair Management System, migrating all Studio customisations to a proper Python/XML module.

## Steering Documents Compliance
- **Module Standards:** Standard Odoo module directory layout; descriptive filenames without module
  prefix
- **Technology Stack:** Python 3.10+, Odoo 17 Enterprise, PostgreSQL 14+; no deprecated APIs
- **Business Rules:** Repair lifecycle enforced via method guards; RUG approval mandatory for RUG
  repairs; cancel/reopen audit trail immutable

## Atomic Task Requirements
Each task modifies at most 1-3 closely related files, is completable in 15-30 minutes, implements
one testable Odoo feature or component, and follows Odoo 17 coding conventions (no `attrs=`, no
`@api.multi`, use domain expressions for `invisible`/`required`/`readonly`).

---

## Phase 1: Module Foundation

- [x] 1.1. Create module scaffold — `__manifest__.py`, `__init__.py`, directory structure
  - Files to create:
    - `jinstage_helpdesk_repair/__manifest__.py`
    - `jinstage_helpdesk_repair/__init__.py`
    - `jinstage_helpdesk_repair/models/__init__.py`
    - `jinstage_helpdesk_repair/views/` (empty directory placeholder)
    - `jinstage_helpdesk_repair/security/` (empty directory placeholder)
    - `jinstage_helpdesk_repair/data/` (empty directory placeholder)
    - `jinstage_helpdesk_repair/report/` (empty directory placeholder)
    - `jinstage_helpdesk_repair/tests/__init__.py`
    - `jinstage_helpdesk_repair/static/description/` (empty placeholder)
  - Implementation steps:
    - Define `__manifest__.py` with name, version `17.0.1.0.0`, category `Helpdesk`,
      author `Jinasena Pvt Ltd`, licence `LGPL-3`
    - Set `depends` list: `['helpdesk', 'helpdesk_fsm', 'helpdesk_sale', 'industry_fsm',
      'stock', 'sale_management', 'account', 'product']`
    - Set `data` list with correct load order (security CSV first, then data, views, reports,
      automation last)
    - Set `installable = True`, `auto_install = False`, `application = False`
    - `__init__.py` imports `models` sub-package
  - Acceptance criteria:
    - Module appears in Apps list in Odoo 17
    - Module installs without errors on a database with all declared dependencies
    - No import errors on Python startup
  - Dependencies: None
  - Complexity: S

- [x] 1.2. Create IR Sequence for repair.seq
  - Files to create:
    - `jinstage_helpdesk_repair/data/ir_sequence_data.xml`
  - Files to modify:
    - `jinstage_helpdesk_repair/__manifest__.py` — add to `data` list
  - Implementation steps:
    - Create `ir.sequence` record with:
      - `code = 'repair.seq'`
      - `name = 'Repair Sequence'`
      - `prefix = 'REP/%(year)s/'`
      - `padding = 5`
      - `number_increment = 1`
      - `use_date_range = False`
      - `company_id = False` (global sequence)
    - Verify sequence appears in Odoo Settings > Sequences after module install
  - Acceptance criteria:
    - `env['ir.sequence'].next_by_code('repair.seq')` returns a value in format `REP/2026/00001`
    - Sequence increments correctly on each call
    - Sequence does not reset between calls without date range
  - Dependencies: Task 1.1
  - Complexity: S
  - _Requirements: FR-001_

- [x] 1.3. Create Repair Diagnosis master data models
  - Files to create:
    - `jinstage_helpdesk_repair/models/repair_symptom_area.py`
    - `jinstage_helpdesk_repair/models/repair_symptom_code.py`
    - `jinstage_helpdesk_repair/models/repair_condition.py`
    - `jinstage_helpdesk_repair/models/repair_diagnosis_area.py`
    - `jinstage_helpdesk_repair/models/repair_diagnosis_code.py`
    - `jinstage_helpdesk_repair/models/repair_reason.py`
    - `jinstage_helpdesk_repair/models/repair_reason_customer.py`
    - `jinstage_helpdesk_repair/models/repair_sub_reason.py`
    - `jinstage_helpdesk_repair/models/repair_resolution.py`
  - Files to modify:
    - `jinstage_helpdesk_repair/models/__init__.py` — add imports for all 9 models
  - Implementation steps:
    - Each model: `_name = 'jinstage.repair.<entity>'`, inherits `models.Model`
    - Common fields: `name (Char, required, translate=True)`, `code (Char)`,
      `description (Text, optional)`, `active (Boolean, default=True)`
    - Hierarchical models: `symptom_code` has `Many2one → symptom_area`; `diagnosis_code`
      has `Many2one → diagnosis_area`; `sub_reason` has `Many2one → reason`
    - Add `_sql_constraints` for unique `code` where applicable
    - Set `_order = 'name'` on all models
  - Acceptance criteria:
    - All 9 models appear in Odoo developer mode under Technical > Models
    - Records can be created/edited/deleted via the Odoo ORM
    - Hierarchical relationships (symptom_code → symptom_area) resolve correctly
    - `active` field supports archive/unarchive
  - Dependencies: Task 1.1
  - Complexity: M
  - _Requirements: FR-013_

- [x] 1.4. Create access rights — `ir.model.access.csv`
  - Files to create:
    - `jinstage_helpdesk_repair/security/ir.model.access.csv`
  - Files to modify:
    - `jinstage_helpdesk_repair/__manifest__.py` — confirm CSV is first in `data` list
  - Implementation steps:
    - Add two rows per diagnosis model (user read-only, manager full access):
      Models: `jinstage_repair_symptom_area`, `jinstage_repair_symptom_code`,
      `jinstage_repair_condition`, `jinstage_repair_diagnosis_area`,
      `jinstage_repair_diagnosis_code`, `jinstage_repair_reason`,
      `jinstage_repair_reason_customer`, `jinstage_repair_sub_reason`,
      `jinstage_repair_resolution`
    - User group: `helpdesk.group_helpdesk_user` — perm_read=1, others=0
    - Manager group: `helpdesk.group_helpdesk_manager` — all permissions=1
    - CSV header: `id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink`
  - Acceptance criteria:
    - Module installs without `AccessError` on any diagnosis model
    - Helpdesk user can read but not create/delete diagnosis records
    - Helpdesk manager can perform all CRUD operations on diagnosis records
  - Dependencies: Tasks 1.1, 1.3
  - Complexity: S
  - _Requirements: FR-013_

---

## Phase 2: Core Model Extensions

- [x] 2.1. Extend `helpdesk.ticket.type` with four repair classification flags
  - Files to create:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket_type.py`
  - Files to modify:
    - `jinstage_helpdesk_repair/models/__init__.py` — add import
  - Implementation steps:
    - `_inherit = 'helpdesk.ticket.type'`
    - Add `is_rug = fields.Boolean(string='RUG', default=False)` — True for BOTH Under Warranty types
    - Add `is_rug_confirmed = fields.Boolean(string='RUG Confirmed', default=False)` — True ONLY
      for "Under Warranty - RUG"; False for "External not RUG". This is the key distinguishing flag.
    - Add `is_with_serial_no = fields.Boolean(string='With Serial No', default=False)`
    - Add `is_without_serial_no = fields.Boolean(string='Without Serial No', default=False)`
    - Add help text on `is_rug_confirmed` explaining it gates the full internal approval workflow
    - Create seed data record for each of the four ticket type records in `data/repair_ticket_types.xml`
  - Acceptance criteria:
    - `helpdesk.ticket.type` has four boolean columns: `is_rug`, `is_rug_confirmed`,
      `is_with_serial_no`, `is_without_serial_no`
    - The four seed ticket type records exist with correct flag combinations:
      | Type | is_rug | is_rug_confirmed | is_with_serial_no | is_without_serial_no |
      |---|---|---|---|---|
      | Under Warranty - RUG | ✓ | ✓ | — | — |
      | Under Warranty - External not RUG | ✓ | — | — | — |
      | Not Under Warranty (With Serial No) | — | — | ✓ | — |
      | Not Under Warranty (Without Serial No) | — | — | — | ✓ |
    - All four columns appear on the ticket type tree view
  - Dependencies: Task 1.1
  - Complexity: S
  - _Requirements: FR-002_

- [x] 2.2. Extend `helpdesk.stage` with `company_id` field
  - Files to create:
    - `jinstage_helpdesk_repair/models/helpdesk_stage.py`
  - Files to modify:
    - `jinstage_helpdesk_repair/models/__init__.py` — add import
    - `jinstage_helpdesk_repair/security/record_rules.xml` — create for company rule
  - Implementation steps:
    - `_inherit = 'helpdesk.stage'`
    - Add `company_id = fields.Many2one('res.company', string='Company', tracking=True)`
    - Create `security/record_rules.xml` with domain rule:
      `['|', ('company_id', '=', False), ('company_id', 'in', company_ids)]`
    - Add `record_rules.xml` to `__manifest__.py` data list after security CSV
  - Acceptance criteria:
    - `helpdesk.stage` records have `company_id` column
    - Stages without `company_id` are visible to all companies
    - Stages with `company_id` are only visible to that company's users
    - Record rule `rule_helpdesk_stage_company` exists in Odoo
  - Dependencies: Tasks 1.1, 1.4
  - Complexity: S
  - _Requirements: FR-010_

- [x] 2.3. Extend `helpdesk.ticket` — identification, location, and classification fields
  - Files to create:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
  - Files to modify:
    - `jinstage_helpdesk_repair/models/__init__.py` — add import
  - Implementation steps:
    - `_inherit = 'helpdesk.ticket'`
    - Add identification fields: `repair_serial_no`, `serial_number`, `picking_id`,
      `driver_name`, `vehicle_details`
    - Add location fields: `repair_location`, `return_receipt_location`, `source_location`,
      `job_location`
    - Add four repair type related fields (NOT computed — use `fields.Boolean(related=..., store=True)`):
      - `rug_repair = fields.Boolean(related='ticket_type_id.is_rug', store=True)`
      - `rug_confirmed = fields.Boolean(related='ticket_type_id.is_rug_confirmed', store=True)`
      - `normal_repair_with_serial_no = fields.Boolean(related='ticket_type_id.is_with_serial_no', store=True)`
      - `normal_repair_without_serial_no = fields.Boolean(related='ticket_type_id.is_without_serial_no', store=True)`
    - NOTE: No `_compute_repair_type` method needed — related fields handle propagation automatically
  - Acceptance criteria:
    - All identification and location fields appear on `helpdesk.ticket` database table
    - `rug_repair` is True for both "Under Warranty" ticket types
    - `rug_confirmed` is True ONLY for the "Under Warranty - RUG" type
    - `normal_repair_with_serial_no` is True for "Not Under Warranty (With Serial No)" type
    - `normal_repair_without_serial_no` is True for "Not Under Warranty (Without Serial No)" type
    - Changing ticket type to a different type triggers automatic recompute of all four related booleans
    - All four booleans are stored in DB (`store=True`) for efficient filtering
  - Dependencies: Tasks 1.1, 2.1
  - Complexity: M
  - _Requirements: FR-002, FR-003, FR-004_

- [x] 2.4. Extend `helpdesk.ticket` — workflow status fields, boolean flags, audit fields
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py` — add fields to existing class
  - Implementation steps:
    - Add selection fields: `quick_repair_status`, `cancel_status`, `reopen_status`,
      `re_estimate_status`, `rug_approval_status`, `material_availability`
      (define all selection tuples as per design.md)
    - Add datetime fields: `stage_date`, `cancelled_date`, `reopened_date`
    - Add `cancelled_stage_id = fields.Many2one('helpdesk.stage', ...)`
    - Add all boolean flags: `send_to_centre`, `receive_at_centre`, `send_to_factory`,
      `receive_at_factory`, `handed_over (readonly)`, `fsm_task_done (computed, store=False)`,
      `cancelled`, `cancelled_2`, `repair_serial_created`, `sn_updated`, `rug_confirmed`,
      `rug_approved`, `rug_request_sent`, `valid_confirmed_so`, `valid_confirmed2_so`,
      `valid_delivered_so`, `valid_invoiced_so`, `repair_started_stage_updated`,
      `estimation_approved_stage_updated`, `invoice_stage_updated`
    - Add `user_location_validation (computed, store=False)`
    - Add audit user fields: `cancelled_by`, `reopened_by`, `s_received_by`, `f_received_by`,
      `s_shipped_by`, `f_shipped_by` (all `Many2one → res.users`)
    - Add `created_by_1` through `created_by_10` (`Many2one → res.users`)
    - Implement `_compute_fsm_task_done` with `@api.depends('task_ids',
      'task_ids.stage_id', 'task_ids.stage_id.is_closed')`
    - Implement `_compute_user_location_validation` (no store, checks `env.user` against
      `repair_location.users_stock_location`)
    - Override `write` to set `stage_date` when `stage_id` changes
  - Acceptance criteria:
    - All boolean flags default to False on new tickets
    - `fsm_task_done` is True when all linked project.task records have `stage_id.is_closed = True`
    - `user_location_validation` is True when `repair_location.users_stock_location` is empty
      OR `env.user` is in the permitted users list
    - `stage_date` is updated to `now()` whenever `stage_id` changes on write
    - `rug_approval_status` selection shows three values: Pending, Approved, Rejected
  - Dependencies: Task 2.3
  - Complexity: L
  - _Requirements: FR-006, FR-007, FR-008, FR-009, FR-018, FR-019_

- [x] 2.5. Extend `helpdesk.ticket` — financial fields, document fields, and picking smart button
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py` — add remaining fields
  - Implementation steps:
    - Add financial fields: `balance_due (Float)`, `sales_price (Char)`, `unit_price (Float)`,
      `quantity (Integer, default=1)`, `qty (Char)`
    - Add `items = fields.Many2many('product.product', ...)` with explicit relation table name
      `helpdesk_ticket_product_rel`
    - Add document fields: `warranty_card (Binary, attachment=True)`,
      `related_information (Binary, attachment=True)`
    - Add `sale_order = fields.Many2one('sale.order', compute='_compute_sale_order', store=True)`
    - Implement `_compute_sale_order` with `@api.depends('task_ids', 'task_ids.sale_order_id')`
      — extract first SO from FSM tasks
    - Add `picking_ids = fields.Many2many('stock.picking', compute='_compute_picking_ids')`
    - Add `picking_count = fields.Integer(compute='_compute_picking_ids')`
    - Implement `_compute_picking_ids` using `search([('helpdesk_ticket_id', '=', self.id)])`
    - Add SO lifecycle flags: `valid_confirmed_so`, `valid_confirmed2_so`, `valid_delivered_so`,
      `valid_invoiced_so`, `invoice_stage_updated` (if not already added in 2.4)
  - Acceptance criteria:
    - `items` Many2many uses relation table `helpdesk_ticket_product_rel` (no name collision)
    - `sale_order` computed field is populated when a linked FSM task has `sale_order_id`
    - `picking_count` returns the count of `stock.picking` records where
      `helpdesk_ticket_id = ticket.id`
    - `warranty_card` and `related_information` are stored as attachments
  - Dependencies: Task 2.4
  - Complexity: M
  - _Requirements: FR-005, FR-011, FR-012, FR-018_

---

## Phase 3: Business Logic Methods

- [x] 3.1. Implement repair type classification logic (onchange and UI guards)
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
  - Implementation steps:
    - NOTE: The four type booleans (`rug_repair`, `rug_confirmed`, `normal_repair_with_serial_no`,
      `normal_repair_without_serial_no`) are related fields — no `_compute_repair_type` method needed.
    - Add `@api.onchange('ticket_type_id')` to clear `repair_serial_no` when type changes
      to one where `is_with_serial_no = False` (i.e. not a serial-tracked repair)
    - Verify stored related fields recompute on `ticket_type_id` write in tests
    - Add comment block in model documenting the four type combinations and their flag values
  - Acceptance criteria:
    - Changing ticket type to "Under Warranty - RUG" sets `rug_repair = True`, `rug_confirmed = True`
    - Changing ticket type to "Under Warranty - External not RUG" sets `rug_repair = True`,
      `rug_confirmed = False`
    - Changing ticket type to a non-serial type clears `repair_serial_no` via onchange
    - Exactly one of the four branch booleans is True per ticket (enforced by type flag matrix)
  - Dependencies: Tasks 2.3, 2.4
  - Complexity: S
  - _Requirements: FR-002_

- [x] 3.2. Implement serial number management methods
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
  - Implementation steps:
    - Implement `action_create_serial_number(self)`:
      - `ensure_one()`
      - Guard: raise `UserError` if `repair_serial_created = True`
      - NOTE (FR-003 update): The guard blocking creation for `normal_repair_without_serial_no`
        type is REMOVED. The method is now available for all repair types. For the
        "Without Serial No" type, the created serial is an internal reference only.
      - Create `stock.lot` with `name = self.name`, appropriate `product_id` and `company_id`
      - Write `repair_serial_no = lot.id`, `repair_serial_created = True`
    - Add `@api.onchange('repair_serial_no')` to set `sn_updated = True` when the field changes
      on an existing record (check `self._origin.repair_serial_no` vs new value)
  - Acceptance criteria:
    - `action_create_serial_number` creates a `stock.lot` and links it to the ticket
    - Calling `action_create_serial_number` a second time raises `UserError`
    - `sn_updated` becomes True when `repair_serial_no` is changed after initial creation
    - Serial creation IS available for `normal_repair_without_serial_no = True` tickets
      (creates an internal reference serial, not blocked)
  - Dependencies: Task 2.3
  - Complexity: S
  - _Requirements: FR-003_

- [x] 3.3. Implement cancel and reopen workflow methods
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
  - Implementation steps:
    - Implement `action_cancel_ticket(self)`:
      - `ensure_one()`
      - Guard: raise `UserError` if `self.cancelled = True`
      - Write: `cancelled = True`, `cancelled_date = fields.Datetime.now()`,
        `cancelled_by = self.env.uid`, `cancelled_stage_id = self.stage_id.id`
    - Implement `action_reopen_ticket(self)`:
      - `ensure_one()`
      - Guard: raise `UserError` if `self.cancelled = False`
      - Write: `cancelled = False`, `reopened_date = fields.Datetime.now()`,
        `reopened_by = self.env.uid`
  - Acceptance criteria:
    - `action_cancel_ticket` sets all four cancel audit fields atomically
    - Cancelled ticket shows `cancelled = True` and has `cancelled_by` populated
    - Re-cancelling an already-cancelled ticket raises `UserError`
    - `action_reopen_ticket` clears `cancelled` and records reopen audit fields
    - Reopening a non-cancelled ticket raises `UserError`
  - Dependencies: Task 2.4
  - Complexity: S
  - _Requirements: FR-008_

- [x] 3.4. Implement RUG approval workflow methods
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
  - Implementation steps:
    - Implement `action_send_rug_request(self)` (FR-007 — TIMING CHANGE):
      - `ensure_one()`
      - Guard: raise `UserError` if `not self.rug_repair or not self.rug_confirmed`
        (only "Under Warranty - RUG" type goes through approval)
      - Guard: raise `UserError` if `not self.sale_order`
        (quotation must exist — RUG approval happens AFTER quotation, BEFORE customer SO confirmation)
      - Guard: raise `UserError` if `self.rug_request_sent`
      - Write: `rug_request_sent = True`, `rug_approval_status = 'pending'`
    - Implement `action_approve_rug(self)`:
      - `ensure_one()`
      - Guard: raise `UserError` if `rug_approval_status != 'pending'`
      - Write: `rug_approval_status = 'approved'`, `rug_approved = True`
      - NOTE: Do NOT write `rug_confirmed` — it is a related field from the ticket type
    - Implement `action_reject_rug(self)`:
      - `ensure_one()`
      - Guard: raise `UserError` if `rug_approval_status != 'pending'`
      - Write: `rug_approval_status = 'rejected'`, `rug_approved = False`
    - NOTE (FR-007 update): `action_send_to_factory` does NOT guard on RUG approval.
      The factory gate is removed. RUG approval now gates SO confirmation (not factory dispatch).
  - Acceptance criteria:
    - `action_send_rug_request` sets `rug_request_sent = True` and `status = 'pending'`
    - Sending request on "External not RUG" ticket (rug_confirmed=False) raises `UserError`
    - Sending request when `sale_order` is not set raises `UserError`
    - Sending request twice raises `UserError`
    - `action_approve_rug` sets `rug_approved = True` only (NOT `rug_confirmed`)
    - `action_reject_rug` sets `rug_approval_status = 'rejected'`
    - `action_send_to_factory` does NOT block on RUG approval — factory gate removed
    - "External not RUG" tickets can call `action_send_to_factory` without approval
  - Dependencies: Tasks 2.4, 3.3
  - Complexity: M
  - _Requirements: FR-007_

- [x] 3.5. Extend `stock.picking` and implement `action_create_repair_route` (Return Transfer)
  - Files to create:
    - `jinstage_helpdesk_repair/models/stock_picking.py`
  - Files to modify:
    - `jinstage_helpdesk_repair/models/__init__.py` — add import
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py` — implement route method
    - `jinstage_helpdesk_repair/security/ir.model.access.csv` — no new model; existing
      `stock.picking` access sufficient (verify)
  - Implementation steps:
    - In `stock_picking.py`: `_inherit = 'stock.picking'`
    - Add `helpdesk_ticket_id = fields.Many2one('helpdesk.ticket', string='Repair Ticket',
      ondelete='set null', index=True)`
    - In `helpdesk_ticket.py`, implement `action_create_repair_route(self)`:
      - NOTE (FR-005 update): This is a REVERSE TRANSFER (return picking) that receives the
        defective item into the repair location. A popup dialog confirms the return location.
      - `ensure_one()`
      - Guard: raise `UserError` if `picking_count > 0` (transfer already created)
      - Guard: raise `UserError` if required location fields not set
      - Determine `picking_type_id` from `repair_location`'s warehouse
      - Create inbound reverse `stock.picking` with `helpdesk_ticket_id = self.id`
      - Set `self.picking_id` to the created picking
    - Implement `action_view_pickings(self)` returning an `ir.actions.act_window` action
      named "Repair Transfers" filtered to `('helpdesk_ticket_id', '=', self.id)`
  - Acceptance criteria:
    - `stock.picking` has `helpdesk_ticket_id` column in database
    - `action_create_repair_route` creates a return transfer picking linked to the ticket
    - Calling route creation twice raises `UserError`
    - `action_view_pickings` returns an action named "Repair Transfers" opening filtered list
    - Smart button shows "Repair Trans" label (not "Pickings")
    - `picking_count` smart button shows correct count
  - Dependencies: Tasks 2.3, 2.5
  - Complexity: M
  - _Requirements: FR-005_

---

## Phase 4: Location and Transfer Logic

- [x] 4.1. Implement factory and sales centre transfer tracking methods
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
  - Implementation steps:
    NOTE (FR-006 update): CORRECT ORDER IS factory FIRST, sales centre AFTER repair.

    - Implement `action_send_to_factory(self)` (replaces old centre-first logic):
      - Guard: `picking_count == 0` → raise `UserError('Create return transfer first.')`
        NOTE: Only `picking_count > 0` required — NO centre prerequisite!
        NOTE: NO RUG approval gate — approval now gates SO confirmation, not factory dispatch.
      - Write: `send_to_factory = True`, `f_shipped_by = self.env.uid`,
        `stage_date = fields.Datetime.now()`
    - Implement `action_receive_at_factory(self)`:
      - Guard: `not send_to_factory` → `UserError`
      - Guard: `receive_at_factory` already True → `UserError`
      - Write: `receive_at_factory = True`, `f_received_by = self.env.uid`,
        `stage_date = fields.Datetime.now()`
    - Implement `action_send_to_centre(self)` (sales centre AFTER repair completion):
      - Guard: `not receive_at_factory` → `UserError('Item must be received at factory first.')`
        NOTE: `receive_at_factory` must be True — factory/repair complete before sales centre dispatch.
      - Write: `send_to_centre = True`, `s_shipped_by = self.env.uid`,
        `stage_date = fields.Datetime.now()`
    - Implement `action_receive_at_centre(self)`:
      - Guard: `not send_to_centre` → `UserError`
      - Guard: `receive_at_centre` already True → `UserError`
      - Write: `receive_at_centre = True`, `s_received_by = self.env.uid`,
        `stage_date = fields.Datetime.now()`
  - Acceptance criteria:
    - Factory flags require only `picking_count > 0` (no centre prerequisite)
    - Sales centre flags require `receive_at_factory = True` (factory/repair complete first)
    - Within each leg: send before receive is enforced
    - User tracking fields populated with `env.user` at time of action
    - `stage_date` updated on each movement action
    - All prerequisite guards raise `UserError` with descriptive message
  - Dependencies: Task 3.4
  - Complexity: S
  - _Requirements: FR-006_

- [x] 4.2. Extend `stock.location` with `users_stock_location` and user validation logic
  - Files to create:
    - `jinstage_helpdesk_repair/models/stock_location.py`
  - Files to modify:
    - `jinstage_helpdesk_repair/models/__init__.py` — add import
    - `jinstage_helpdesk_repair/security/ir.model.access.csv` — add row for
      stock.location user access if not already covered by stock module
  - Implementation steps:
    - In `stock_location.py`: `_inherit = 'stock.location'`
    - Add `users_stock_location = fields.Many2many('res.users',
      relation='stock_location_users_rel', column1='location_id', column2='user_id',
      string='Permitted Users')`
    - Ensure `_compute_user_location_validation` in `helpdesk_ticket.py` (added in 2.4)
      correctly reads `self.repair_location.users_stock_location`
    - Test: empty `users_stock_location` means all users pass validation
    - Test: non-empty list restricts to listed users only
  - Acceptance criteria:
    - `stock.location` has `users_stock_location` Many2many in database
    - `user_location_validation = True` when `users_stock_location` is empty
    - `user_location_validation = False` when current user not in `users_stock_location`
    - `user_location_validation = True` when current user IS in `users_stock_location`
  - Dependencies: Task 2.4
  - Complexity: S
  - _Requirements: FR-009_

- [x] 4.3. FSM task integration — `fsm_task_done` and `sale_order` computed fields
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
  - Implementation steps:
    - Review and finalise `_compute_fsm_task_done`:
      - `@api.depends('task_ids', 'task_ids.stage_id', 'task_ids.stage_id.is_closed')`
      - `fsm_task_done = all(t.stage_id.is_closed for t in ticket.task_ids) if ticket.task_ids else False`
    - Review and finalise `_compute_sale_order`:
      - `@api.depends('task_ids', 'task_ids.sale_order_id')`
      - Defensive: `sale_order = ticket.task_ids.mapped('sale_order_id')[:1]`
    - Verify `handed_over` field is set via `action_receive_at_factory` or a dedicated
      `action_handover` method
    - Implement `action_view_fsm_tasks(self)` — return `ir.actions.act_window` for FSM tasks
      filtered to `('helpdesk_ticket_ids', 'in', [self.id])` (or existing helpdesk_fsm action)
  - Acceptance criteria:
    - `fsm_task_done` is True only when at least one FSM task exists and all are in a closed stage
    - `fsm_task_done` is False when no FSM tasks exist
    - `sale_order` is populated from the first FSM task's `sale_order_id`
    - `sale_order` is empty when no FSM tasks have a sale order
    - FSM task smart button shows count of linked tasks
  - Dependencies: Task 2.5
  - Complexity: M
  - _Requirements: FR-018_

---

## Phase 5: Views

- [x] 5.1. Helpdesk ticket form view — header, smart buttons, Repair Info tab, Cancel/Reopen tab
  - Files to create:
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
  - Files to modify:
    - `jinstage_helpdesk_repair/__manifest__.py` — add view file to data list
  - Implementation steps:
    - Create `ir.ui.view` with `inherit_id = 'helpdesk.helpdesk_ticket_view_form'`
    - Inject smart button ("Repair Trans" — NOT "Pickings") into `//div[@name='button_box']`
    - Inject all 9 action buttons into `//header` using `invisible=` domain expressions
      (Odoo 17 syntax — not `attrs=`). CORRECT MOVEMENT ORDER: factory first, centre after repair.
      - Create Return Transfer: `invisible="picking_count > 0"`
      - Send to Factory: `invisible="send_to_factory or picking_count == 0"`
        (requires only picking_count > 0 — NO centre prerequisite)
      - Receive at Factory: `invisible="receive_at_factory or not send_to_factory"`
      - Plan Intervention: `invisible="not receive_at_factory or repair_started_stage_updated"`
        (requires receive_at_factory=True; method also guards repair_reason_id)
      - Send RUG Request: `invisible="not rug_confirmed or rug_request_sent"`
        (requires sale_order to be set — enforced server-side in action method)
      - Send to Sales Centre: `invisible="send_to_centre or not receive_at_factory"`
        (requires receive_at_factory=True — repair complete before sales centre dispatch)
      - Receive at Sales Centre: `invisible="receive_at_centre or not send_to_centre"`
      - Cancel: `invisible="cancelled"`
      - Reopen: `invisible="not cancelled"`
    - Inject `<page name="repair_info" string="Repair Info">` before description tab
    - Add repair classification group (includes `repair_reason_id`), serial group,
      vehicle/financial group, documents group, materials group within the new tab
    - Inject Cancel/Reopen Log tab inside `//notebook` (at end)
    - Use `invisible="1"` for hidden computed/flag fields needed by domain expressions
  - Acceptance criteria:
    - Form view loads without XML parse errors
    - All 9 buttons show/hide correctly based on field values and correct movement order
    - "Repair Trans" smart button shows count (not "Pickings")
    - `repair_reason_id` field visible in Repair Info tab
    - Repair Info tab displays all repair-specific fields
    - Cancel/Reopen Log tab shows audit fields
    - No `attrs=` syntax used anywhere in the view (Odoo 17 compliance)
  - Dependencies: Tasks 2.3, 2.4, 2.5, 3.1 through 3.5
  - Complexity: L
  - _Requirements: FR-002, FR-003, FR-005, FR-006, FR-007, FR-008, FR-011, FR-012, FR-013, FR-014_

- [x] 5.2. Helpdesk ticket Extra Info tab injection, kanban view, and list view
  - Files to modify:
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml` — add more records
  - Implementation steps:
    - In the form view inheritance, inject into `//page[@name='extra_info']`:
      - Separator "Repair Locations" with four location fields
      - Separator "Workflow Status" with status selections and boolean flags
      - Separator "Sale Order Flags" with SO lifecycle fields
      - Separator "Tracking" with user tracking fields (readonly)
    - Create kanban view extension (`inherit_id = 'helpdesk.helpdesk_ticket_view_kanban'`):
      - Inject `rug_repair`, `normal_repair_with_serial_no`, `quick_repair_status` field
        declarations
      - Inject repair badge div into kanban card body (after existing details)
      - Badge classes: `text-bg-warning` for RUG, `text-bg-info` for serial,
        `text-bg-secondary` for no serial
    - Create list view extension (`priority = 900`,
      `inherit_id = 'helpdesk.helpdesk_tickets_view_list'`):
      - Add `decoration-muted="cancelled == True"` attribute to `//list`
      - Insert repair columns after `name`: `rug_repair`, `normal_repair_with_serial_no`,
        `repair_serial_no`, `repair_location`
      - Insert after `stage_id`: `rug_approval_status`, `material_availability`,
        `balance_due`, `send_to_centre`, `receive_at_centre`, `send_to_factory`,
        `receive_at_factory`, `stage_date`
      - Set `optional="show"` on all new columns
  - Acceptance criteria:
    - Extra Info tab shows all four location fields and workflow status flags
    - Kanban cards display repair type badge in correct colour
    - List view shows repair-specific columns with `optional="show"`
    - Cancelled tickets are visually muted in list view
    - No `attrs=` used in any view
  - Dependencies: Task 5.1
  - Complexity: M
  - _Requirements: FR-016, FR-017_

- [x] 5.3. Stage, ticket type, and team view extensions
  - Files to create:
    - `jinstage_helpdesk_repair/views/helpdesk_stage_views.xml`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_type_views.xml`
  - Files to modify:
    - `jinstage_helpdesk_repair/__manifest__.py` — add both files to data list before ticket views
  - Implementation steps:
    - Stage form extension: inject `company_id` after `name` field
    - Stage tree extension: inject `company_id` column with `optional="show"`
    - Ticket type tree extension: inject `is_rug`, `is_rug_confirmed`, `is_with_serial_no`,
      and `is_without_serial_no` columns with `optional="show"`
    - Verify `inherit_id` references (check exact XML IDs in helpdesk module):
      - `helpdesk.helpdesk_stage_view_form`
      - `helpdesk.helpdesk_stage_view_list`
      - `helpdesk.helpdesk_ticket_type_view_list`
  - Acceptance criteria:
    - Stage form view shows `company_id` field
    - Stage list view has optional `company_id` column
    - Ticket type list shows optional `is_rug`, `is_rug_confirmed`, `is_with_serial_no`,
      `is_without_serial_no` columns (four-flag matrix visible in list)
    - All views load without errors in Odoo UI
  - Dependencies: Tasks 2.1, 2.2
  - Complexity: S
  - _Requirements: FR-002, FR-010_

- [x] 5.4. Diagnosis master data views
  - Files to create:
    - `jinstage_helpdesk_repair/views/diagnosis_views.xml`
  - Files to modify:
    - `jinstage_helpdesk_repair/__manifest__.py` — add to data list
  - Implementation steps:
    - Create tree (editable="top") and form views for all 9 diagnosis models
    - Tree view fields: `name`, `code`, `active` (optional), parent M2o (where applicable)
    - Form view fields: `name`, `code`, `active`, `description`, parent M2o (where applicable)
    - Use consistent `ir.ui.view` naming: `jinstage.repair.<entity>.list` and
      `jinstage.repair.<entity>.form`
    - Do not create `ir.actions.act_window` here — those go in `actions.xml` (Task 5.5)
  - Acceptance criteria:
    - All 9 models have working list and form views
    - Hierarchical fields (symptom area on symptom code, etc.) appear as Many2one dropdowns
    - `active` field supports filtering archived records
    - Views accessible via Odoo developer mode "Edit View" button
  - Dependencies: Task 1.3
  - Complexity: M
  - _Requirements: FR-013_

- [x] 5.5. Actions and menu structure
  - Files to create:
    - `jinstage_helpdesk_repair/views/actions.xml`
    - `jinstage_helpdesk_repair/views/menus.xml`
  - Files to modify:
    - `jinstage_helpdesk_repair/__manifest__.py` — add both files after diagnosis_views.xml
  - Implementation steps:
    - In `actions.xml`: create `ir.actions.act_window` for each of the 9 diagnosis models,
      the 2 active reporting actions, and the 2 inactive reporting actions
    - Reporting actions domain examples:
      - `action_repair_job_details`: all tickets (no domain filter, user applies manually)
      - `action_repair_so_list`: filter where `sale_order != False`
      - `action_repair_job_details_rug`: filter where `rug_repair = True`
    - In `menus.xml`: create all menu items as per design.md:
      - Under `helpdesk.helpdesk_menu_configuration`:
        - `menu_repair_diagnosis_root` (parent) with group `helpdesk.group_helpdesk_manager`
        - 9 diagnosis sub-menus
        - `menu_repair_stages`
        - `menu_repair_accounts`
      - Under `helpdesk.helpdesk_menu_reporting`:
        - `menu_repair_job_details` (active)
        - `menu_repair_so_list` (active)
        - `menu_repair_job_details_rug` (`active="0"`)
        - `menu_customer_letter_report` (`active="0"`)
  - Acceptance criteria:
    - All 9 diagnosis tables accessible under Helpdesk > Configuration > Repair Diagnosis
    - Repair Diagnosis root menu only visible to helpdesk managers
    - Two active reporting menus visible under Helpdesk > Reporting
    - Two inactive menus do not appear until manually activated
    - All `ir.actions.act_window` actions reference correct models and views
  - Dependencies: Tasks 5.3, 5.4
  - Complexity: M
  - _Requirements: FR-013, FR-020_

---

## Phase 6: Reports

- [x] 6.1. Repair Receipt and Repair Status report templates
  - Files to create:
    - `jinstage_helpdesk_repair/report/report_repair_receipt.xml`
    - `jinstage_helpdesk_repair/report/report_repair_status.xml`
    - `jinstage_helpdesk_repair/report/paper_formats.xml`
    - `jinstage_helpdesk_repair/report/report_actions.xml` (partial — start with these 2 actions)
  - Files to modify:
    - `jinstage_helpdesk_repair/__manifest__.py` — add report files
  - Implementation steps:
    - `paper_formats.xml`: create `report.paperformat` record `paperformat_eur_a4` (A4, Portrait,
      10mm margins)
    - `report_actions.xml`: create `ir.actions.report` records for Repair Receipt (US Letter)
      and Repair Status (Default)
    - Both reports use `report_type='qweb-pdf'`, `binding_model_id = helpdesk.model_helpdesk_ticket`
    - `report_repair_receipt.xml`: QWeb template with `t-call="web.html_container"` and
      `t-call="web.external_layout"`; display ticket name, partner, date, repair type, serial,
      location, balance due, signature lines
    - `report_repair_status.xml`: internal status report; display all movement flags
      (send_to_centre, receive_at_centre, etc.), stage, RUG approval status, assigned users
  - Acceptance criteria:
    - Reports appear in Print menu on helpdesk ticket form
    - PDF generates without errors for a sample repair ticket
    - Repair Receipt uses US Letter format
    - Repair Status uses default format (A4)
    - Company logo appears via `web.external_layout`
  - Dependencies: Tasks 2.3, 2.4
  - Complexity: M
  - _Requirements: FR-014_

- [x] 6.2. Repair Final Notice and Repair Final Notice Scrappage templates
  - Files to create:
    - `jinstage_helpdesk_repair/report/report_repair_final_notice.xml`
    - `jinstage_helpdesk_repair/report/report_repair_final_notice_scrappage.xml`
  - Files to modify:
    - `jinstage_helpdesk_repair/report/report_actions.xml` — add two more report actions
  - Implementation steps:
    - `report_repair_final_notice.xml`: customer-facing completion notice; display repair
      reference, customer name, serial number, repair description (from ticket description),
      completion date, items list, amount due, signature area; use EUR A4 paper format
    - `report_repair_final_notice_scrappage.xml`: scrappage write-off notice; display same
      header but with "This item has been assessed as beyond economic repair" message;
      use US Letter format
    - Report actions: Repair Final Notice with `paperformat_id = paperformat_eur_a4`,
      Scrappage with `paperformat_id = base.paperformat_us`
    - Both use `binding_type = 'report'` to appear in Print menu
  - Acceptance criteria:
    - Both reports generate PDF without errors
    - Final Notice uses EUR A4 format
    - Scrappage uses US Letter format
    - Scrappage report includes appropriate scrappage language
    - Serial number field conditional: only shown when `repair_serial_no` is set
  - Dependencies: Task 6.1
  - Complexity: M
  - _Requirements: FR-014_

- [x] 6.3. Helpdesk Ticket Report template and finalise all report actions
  - Files to create:
    - `jinstage_helpdesk_repair/report/report_helpdesk_ticket.xml`
  - Files to modify:
    - `jinstage_helpdesk_repair/report/report_actions.xml` — add final report action
  - Implementation steps:
    - `report_helpdesk_ticket.xml`: comprehensive full-ticket printout; include all repair
      fields (type, serial, locations, financial, items list, workflow flags, cancel/reopen
      history); use default paper format
    - Report action: `ir.actions.report` for Helpdesk Ticket Report with default paper format
    - Verify all 5 report actions are in `report_actions.xml` with correct `report_name`
      references (must match template `id` attributes in respective XML files)
    - Test all 5 reports from the Print menu on a ticket that has all field types populated
  - Acceptance criteria:
    - All 5 reports appear in ticket form Print menu
    - Helpdesk Ticket Report includes cancel/reopen history from audit fields
    - No broken field references (all `t-field` values correspond to actual ticket fields)
    - Reports work for both RUG and Normal repair types without errors
  - Dependencies: Tasks 6.1, 6.2
  - Complexity: M
  - _Requirements: FR-014_

---

## Phase 7: Automation and Security

- [x] 7.1. Automation rules — company in stage, repair sequence, location validation
  - Files to create:
    - `jinstage_helpdesk_repair/data/automation_rules.xml`
  - Files to modify:
    - `jinstage_helpdesk_repair/__manifest__.py` — add automation_rules.xml LAST in data list
      (after all model views are registered)
  - Implementation steps:
    - Create `base.automation` record `automation_company_in_stage`:
      - model: `helpdesk.stage`, trigger: `on_write`, active: True
      - code: reads `allowed_company_ids` from context, sets `record.company_id`
    - Create `base.automation` record `automation_repair_sequence`:
      - model: `helpdesk.ticket`, trigger: `on_create`, filter: `[('name', '=', 'New')]`
      - code: `if record.name == 'New': record.write({'name': env['ir.sequence'].next_by_code('repair.seq')})`
      - active: True
    - Create `base.automation` record `automation_location_validation`:
      - model: `helpdesk.ticket`, trigger: `on_write`, active: False
      - code: location permission check raising `UserError` if user not in permitted list
    - Verify automation rule trigger fields match Odoo 17 `base.automation` field names
      (use `trigger` field, not deprecated `kind`)
  - Acceptance criteria:
    - New tickets created with default name "New" receive sequence `REP/YYYY/NNNNN`
    - New stages created via UI get `company_id` from context automatically
    - Location validation rule exists in database but is inactive
    - Activating location validation rule enforces location permission on ticket write
  - Dependencies: Tasks 1.2, 2.2
  - Complexity: M
  - _Requirements: FR-001, FR-010, FR-009_

- [x] 7.2. Reverse Transfer approval rule configuration
  - Files to create (choose approach based on Odoo 17 `approval` module availability):
    - Option A (approval module): `data/approval_rules.xml`
    - Option B (group-restricted button): extend `stock_picking.py` with group check method
  - Files to modify:
    - `jinstage_helpdesk_repair/__manifest__.py` — add approval module to `depends` if using
      Option A, or add `data/approval_rules.xml` to data list
  - Implementation steps:
    - **Option A** (preferred if `approval` module available):
      - Create `approval.rule` or equivalent Odoo 17 record requiring `base.group_user` approval
        before validating a reverse transfer picking
      - Link rule to `stock.picking` with `picking_type_code = 'incoming'` and `origin` matching
        return transfers
    - **Option B** (fallback):
      - In `stock_picking.py`, override `button_validate` to check if picking is a return
        (reverse of a repair route picking) and require manager group
      - Raise `UserError` with approval request message if unauthorised user attempts validation
    - Document chosen approach in implementation notes
  - Acceptance criteria:
    - Reverse transfer validation for repair pickings requires approval or manager group
    - Regular stock transfers are unaffected
    - Approval mechanism does not block non-repair reverse transfers
  - Dependencies: Task 3.5
  - Complexity: M
  - _Requirements: FR-015_

- [x] 7.3. Record rules and field-level security review
  - Files to modify:
    - `jinstage_helpdesk_repair/security/record_rules.xml`
  - Files to modify (if gaps found):
    - `jinstage_helpdesk_repair/security/ir.model.access.csv`
  - Implementation steps:
    - Verify `rule_helpdesk_stage_company` (created in 2.2) is correct
    - Review all new models for missing access rights (diagnosis models, stock extensions)
    - Add `ir.rule` for RUG approval: domain restricting `action_approve_rug` and
      `action_reject_rug` buttons to `helpdesk.group_helpdesk_manager` group
      (note: this is view-level `groups=` attribute, not a record rule — add to buttons in 5.1)
    - Confirm `cancelled_by`, `reopened_by`, `s_received_by` etc. are not directly editable
      by users (readonly in view, set only via actions)
    - Review if `handed_over` field requires additional protection (readonly=True in model)
  - Acceptance criteria:
    - Helpdesk user cannot access Repair Diagnosis configuration menus
    - Stage record rule correctly filters by company_id
    - RUG approval buttons visible only to helpdesk managers (add `groups=` attribute to buttons)
    - Audit fields (`cancelled_by`, `cancelled_date`, etc.) are readonly in the form view
  - Dependencies: Tasks 5.1, 7.1
  - Complexity: S
  - _Requirements: FR-007, FR-008, FR-009, FR-010_

---

## Phase 8: Testing

- [x] 8.1. Unit tests for business logic methods
  - Files to create:
    - `jinstage_helpdesk_repair/tests/test_repair_workflow.py`
  - Files to modify:
    - `jinstage_helpdesk_repair/tests/__init__.py` — import test module
  - Implementation steps:
    - Class `TestRepairTypeClassification(TransactionCase)`:
      - `test_under_warranty_rug_flags`: create ticket with "Under Warranty - RUG" type →
        verify `rug_repair = True`, `rug_confirmed = True`,
        `normal_repair_with_serial_no = False`, `normal_repair_without_serial_no = False`
      - `test_external_not_rug_flags`: create ticket with "Under Warranty - External not RUG" →
        verify `rug_repair = True`, `rug_confirmed = False`
      - `test_normal_serial_type_flags`: verify `normal_repair_with_serial_no = True`
      - `test_normal_no_serial_type_flags`: verify `normal_repair_without_serial_no = True`
      - `test_type_change_recomputes`: change type from RUG to serial → verify all four booleans
        recomputed correctly
    - Class `TestRepairCancelReopen(TransactionCase)`:
      - `test_cancel_sets_audit_fields`: verify all 4 cancel fields
      - `test_cancel_twice_raises_error`: verify `UserError` on second cancel
      - `test_reopen_clears_cancelled`: verify `cancelled = False` after reopen
      - `test_reopen_non_cancelled_raises_error`: verify `UserError`
    - Class `TestRUGWorkflow(TransactionCase)`:
      - `test_send_rug_request_requires_sale_order`: verify `UserError` when `sale_order` not set
        (RUG approval now requires quotation to exist — FR-007 timing change)
      - `test_send_rug_request_with_sale_order`: set `sale_order`, then verify `rug_request_sent = True`,
        `status = 'pending'`
      - `test_send_rug_request_blocked_for_external`: "External not RUG" ticket →
        verify `UserError` raised when calling `action_send_rug_request`
      - `test_approve_rug`: verify `rug_approved = True` (NOT `rug_confirmed` — that comes from type)
      - `test_reject_rug`: verify `rug_approval_status = 'rejected'`
      - `test_factory_no_longer_blocked_by_rug_approval`: "Under Warranty - RUG" with
        `picking_count > 0` and `rug_approved = False` → verify `action_send_to_factory` SUCCEEDS
        (factory gate removed — FR-007 timing change)
      - `test_external_not_rug_factory_no_approval_needed`: "External not RUG" ticket →
        verify `action_send_to_factory` succeeds WITH a picking present and WITHOUT calling
        `action_approve_rug`
    - Class `TestMovementOrder(TransactionCase)`:
      - `test_factory_requires_return_transfer`: verify `UserError` when `picking_count == 0`
      - `test_centre_requires_receive_at_factory`: verify `UserError` when `receive_at_factory = False`
      - `test_correct_order_factory_then_centre`: simulate full movement sequence:
        create transfer → send to factory → receive at factory → send to centre → receive at centre
    - Class `TestPlanIntervention(TransactionCase)`:
      - `test_plan_intervention_blocked_without_factory`: verify `UserError` when
        `receive_at_factory = False`
      - `test_plan_intervention_blocked_without_reason`: set `receive_at_factory = True`,
        verify `UserError` when `repair_reason_id` not set
      - `test_plan_intervention_success`: set both guards, verify `repair_started_stage_updated = True`
    - Class `TestSerialNumber(TransactionCase)`:
      - `test_create_serial`: verify `stock.lot` created and linked
      - `test_create_serial_twice_raises_error`: verify `UserError`
    - Class `TestStageDate(TransactionCase)`:
      - `test_stage_change_updates_stage_date`: write `stage_id` → verify `stage_date` updated
    - Use `TransactionCase` (not `SavepointCase` — deprecated in Odoo 17)
    - Use `@classmethod setUpClass` for shared test data
  - Acceptance criteria:
    - All test methods pass: `python -m pytest addons/jinstage_helpdesk_repair/tests/ -v`
    - No test depends on UI rendering (pure Python ORM tests)
    - Each test class covers one functional area
    - Tests use `self.assertRaises(UserError)` context manager for error cases
  - Dependencies: Tasks 3.1 through 4.3
  - Complexity: M
  - _Leverage: odoo.tests.common.TransactionCase_
  - _Requirements: FR-001, FR-002, FR-003, FR-007, FR-008, FR-019_

- [x] 8.2. Integration tests for repair workflows
  - Files to create:
    - `jinstage_helpdesk_repair/tests/test_repair_integration.py`
  - Files to modify:
    - `jinstage_helpdesk_repair/tests/__init__.py` — import test module
  - Implementation steps:
    - Class `TestRepairWorkflowA_RUG(TransactionCase)`:
      - `test_full_rug_workflow`: simulate complete "Under Warranty - RUG" lifecycle
        (rug_repair=True, rug_confirmed=True) — CORRECT ORDER: factory first, centre after repair:
        1. Create ticket with "Under Warranty - RUG" type
        2. Call `action_create_repair_route` (return transfer)
        3. Call `action_send_to_factory` — factory directly after intake (NO centre first)
        4. Call `action_receive_at_factory`
        5. Set `repair_reason_id` and call `action_plan_intervention`
        6. Set `sale_order` (simulate quotation), then call `action_send_rug_request`
        7. Call `action_approve_rug` → `rug_approved = True`
        8. (Customer confirms SO — simulated)
        9. Call `action_send_to_centre` — requires `receive_at_factory = True`
        10. Call `action_receive_at_centre`
        11. Verify: `rug_approved = True`, `rug_confirmed = True` (from type),
            `receive_at_factory = True`, `receive_at_centre = True`,
            `repair_started_stage_updated = True`
    - Class `TestRepairWorkflowA2_ExternalNotRUG(TransactionCase)`:
      - `test_full_external_not_rug_workflow`: simulate "Under Warranty - External not RUG"
        lifecycle (rug_repair=True, rug_confirmed=False):
        1. Create ticket with "Under Warranty - External not RUG" type
        2. Verify `rug_repair = True`, `rug_confirmed = False`
        3. Call `action_create_repair_route` (return transfer)
        4. Call `action_send_to_factory` directly — NO approval step required
        5. Call `action_receive_at_factory`
        6. Set `repair_reason_id` and call `action_plan_intervention`
        7. Call `action_send_to_centre` (after factory) → `action_receive_at_centre`
        8. Verify final state: `receive_at_factory = True`, `receive_at_centre = True`,
           `rug_approved = False` (never set)
    - Class `TestRepairWorkflowC_Serial(TransactionCase)`:
      - `test_full_serial_workflow`: simulate "Not Under Warranty (With Serial No)" lifecycle:
        1. Create ticket with serial type (`normal_repair_with_serial_no = True`)
        2. Call `action_create_serial_number`
        3. Verify `repair_serial_created = True` and `stock.lot` created
        4. Call route creation and movement actions
        5. Verify final state flags
    - Class `TestRepairWorkflowD_NoSerial(TransactionCase)`:
      - `test_no_serial_workflow`: simulate "Not Under Warranty (Without Serial No)" flow:
        1. Create ticket with no-serial type (`normal_repair_without_serial_no = True`)
        2. Verify `action_create_serial_number` SUCCEEDS (creates internal reference serial)
           — NOTE: serial creation is no longer blocked for this type (FR-003 update)
        3. Verify `repair_serial_created = True` after serial creation
        4. Complete abbreviated workflow with factory → centre movement order
    - Class `TestMultiCompanyStage(TransactionCase)`:
      - `test_stage_company_scoping`: create stage in company A context → verify
        `company_id` set; switch to company B context → verify stage not visible
  - Acceptance criteria:
    - `test_full_rug_workflow` completes without any exception
    - `test_full_rug_workflow` verifies correct order: factory before centre
    - `test_full_rug_workflow` verifies `rug_approved = True`, `rug_confirmed = True` (from type),
      `receive_at_factory = True`, `receive_at_centre = True`, `repair_started_stage_updated = True`
    - `test_full_external_not_rug_workflow` verifies `rug_approved = False`, `rug_confirmed = False`,
      `receive_at_factory = True` — factory reached without any approval step
    - `test_full_serial_workflow` verifies `repair_serial_created = True` and linked lot
    - `test_no_serial_workflow` verifies `repair_serial_created = True` (serial created as internal
      reference — no longer blocked for this type)
    - Multi-company stage test verifies domain filtering
  - Dependencies: Task 8.1
  - Complexity: M
  - _Leverage: odoo.tests.common.TransactionCase_
  - _Requirements: FR-001 through FR-014 (integration coverage)_

---

## Task Dependency Matrix

| Task | Depends On |
|------|-----------|
| 1.1 | — |
| 1.2 | 1.1 |
| 1.3 | 1.1 |
| 1.4 | 1.1, 1.3 |
| 2.1 | 1.1 |
| 2.2 | 1.1, 1.4 |
| 2.3 | 1.1, 2.1 |
| 2.4 | 2.3 |
| 2.5 | 2.4 |
| 3.1 | 2.3, 2.4 |
| 3.2 | 2.3 |
| 3.3 | 2.4 |
| 3.4 | 2.4, 3.3 |
| 3.5 | 2.3, 2.5 |
| 4.1 | 3.4 |
| 4.2 | 2.4 |
| 4.3 | 2.5 |
| 5.1 | 2.3, 2.4, 2.5, 3.1-3.5 |
| 5.2 | 5.1 |
| 5.3 | 2.1, 2.2 |
| 5.4 | 1.3 |
| 5.5 | 5.3, 5.4 |
| 6.1 | 2.3, 2.4 |
| 6.2 | 6.1 |
| 6.3 | 6.1, 6.2 |
| 7.1 | 1.2, 2.2 |
| 7.2 | 3.5 |
| 7.3 | 5.1, 7.1 |
| 8.1 | 3.1-4.3 |
| 8.2 | 8.1 |
| 9.1 | 3.4, 3.5, 4.1 |
| 9.2 | 3.4, 9.1 |
| 9.3 | 3.2 |
| 9.4 | 3.5, 5.1 |
| 9.5 | 2.4, 2.5 |
| 9.6 | 1.3, 2.3 |
| 9.7 | 4.1, 4.3, 9.6 |
| 9.8 | 9.1-9.7, 8.1, 8.2 |
| 10.1 | 2.3 |
| 10.2 | 2.4, 10.1 |
| 10.3 | 2.5, 4.3 |
| 10.4 | 2.5, 4.2 |
| 10.5 | 2.4, 4.1, 10.12 |
| 10.6 | 2.5, 9.7 |
| 10.7 | 2.4, 3.5, 10.1, 10.2, 10.5 |
| 10.8 | 3.4 |
| 10.9 | 2.1, 3.4, 10.7 |
| 10.10 | 1.2, 3.2 |
| 10.11 | 3.3, 10.12 |
| 10.12 | 2.2 |
| 10.13 | 3.5 |
| 10.14 | 1.3, 1.4, 2.5 |

---

## Odoo 17 Version Compatibility Notes

### Odoo 17 Specific Features Used
- New ORM API: `@api.depends`, `@api.constrains`, `@api.onchange` (all valid)
- `TransactionCase` for tests (not deprecated `SavepointCase`)
- Domain expressions in views: `invisible="field == value"` syntax (not `attrs=`)
- `ir.actions.report` with `report_type='qweb-pdf'`
- `base.automation` with `trigger` field (not deprecated `kind` field)
- `fields.Many2many` with explicit `relation`, `column1`, `column2` to avoid collisions

### Deprecated APIs to Avoid
- `@api.multi` — removed in Odoo 14+
- `@api.one` — removed in Odoo 14+
- `attrs="{'invisible': [...]}"` — deprecated in Odoo 17; use `invisible=` directly
- `states=` attribute on fields — deprecated; use view-level `readonly=` domain
- `_columns` class attribute — replaced by field declarations
- `fields.Date.today()` / `fields.Datetime.now()` as default strings — use lambda defaults

### Key Odoo 17 View Syntax Reference
```xml
<!-- Correct Odoo 17 syntax -->
<field name="stage_id"
       invisible="cancelled == True"
       required="rug_repair == True"
       readonly="handed_over == True"/>

<!-- Wrong (deprecated attrs= syntax) -->
<field name="stage_id"
       attrs="{'invisible': [('cancelled', '=', True)]}"/>
```

---

## Phase 9: Workflow Alignment Fixes

These tasks correct the movement order, RUG approval timing, serial restriction removal, return
transfer relabelling, 50% advance payment, repair reason mandatory gate, and Plan Intervention
action — aligning the implementation with the end-user documentation.

- [x] 9.1. Fix movement order — factory FIRST, sales centre AFTER repair (FR-006)
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
  - Implementation steps:
    - Remove centre prerequisite from `action_send_to_factory`; add `picking_count > 0` guard only
    - Remove RUG approval gate from `action_send_to_factory` (gate moved to SO confirmation)
    - Update `action_send_to_centre` guard: requires `receive_at_factory = True`
    - Update button visibility in XML:
      - Send to Factory: `invisible="send_to_factory or picking_count == 0"` (no centre check)
      - Send to Sales Centre: `invisible="send_to_centre or not receive_at_factory"`
  - Acceptance criteria:
    - `action_send_to_factory` requires only `picking_count > 0`, raises `UserError` if zero
    - `action_send_to_centre` raises `UserError` if `receive_at_factory = False`
    - Buttons show/hide in correct order: factory buttons before centre buttons
  - Dependencies: Tasks 3.4, 3.5, 4.1
  - Complexity: S
  - _Requirements: FR-006_

- [x] 9.2. Fix RUG approval timing — after quotation, before SO confirmation (FR-007)
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
  - Implementation steps:
    - In `action_send_rug_request`: add guard `if not self.sale_order: raise UserError(...)`
    - Remove RUG approval guard from `action_send_to_factory` (no longer gates factory)
    - Document in code: approval flow is Plan Intervention → Add Products → Quotation Created
      → Request RUG Approval → Approved → Customer Confirms SO
  - Acceptance criteria:
    - `action_send_rug_request` raises `UserError` when `sale_order` is not set
    - `action_send_to_factory` no longer raises `UserError` for unapproved RUG tickets
    - Unit test `test_rug_request_requires_sale_order` passes
  - Dependencies: Task 3.4, 9.1
  - Complexity: S
  - _Requirements: FR-007_

- [x] 9.3. Remove serial creation restriction for "Without Serial No" type (FR-003)
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
  - Implementation steps:
    - Remove `if self.normal_repair_without_serial_no: raise UserError(...)` from
      `action_create_serial_number`
    - Update button visibility: remove `or normal_repair_without_serial_no == True` condition
    - Add docstring note: for "Without Serial No" type, created serial is internal reference only
  - Acceptance criteria:
    - `action_create_serial_number` succeeds for all four repair types
    - "Create Serial Number" button visible for all types when `repair_serial_created = False`
    - Unit test confirms serial creation for `normal_repair_without_serial_no = True` tickets
  - Dependencies: Task 3.2
  - Complexity: XS
  - _Requirements: FR-003_

- [x] 9.4. Rename "Create Repair Route" to "Create Return Transfer" and "Pickings" to "Repair Trans" (FR-005)
  - Files to modify:
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py` — update `action_view_pickings` label
  - Implementation steps:
    - Update button string: `string="Create Return Transfer"`
    - Update smart button statinfo string: `string="Repair Trans"`
    - Update `action_view_pickings` return dict: `'name': _('Repair Transfers')`
    - Add popup dialog (wizard or `return_picking_type_id` selection) to confirm return location
      before creating the reverse transfer picking
  - Acceptance criteria:
    - Button shows "Create Return Transfer" on the form header
    - Smart button shows "Repair Trans" label with correct picking count
    - `action_view_pickings` window title is "Repair Transfers"
    - Dialog/popup prompts user to confirm return location before transfer creation
  - Dependencies: Task 3.5, 5.1
  - Complexity: S
  - _Requirements: FR-005_

- [x] 9.5. Add 50% advance payment boolean flag and document two-invoice workflow (FR-012)
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py` — add `advance_invoice_created` field
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml` — add field to Extra Info tab
  - Implementation steps:
    - Add `advance_invoice_created = fields.Boolean(string='Advance Invoice Created',
      default=False, tracking=True)` to `helpdesk.ticket`
    - Display `advance_invoice_created` in the Sale Order Flags group of Extra Info tab
    - Document in code comments the two-invoice workflow:
      SO Confirmed → 50% Advance Invoice (advance_invoice_created=True) → Repair
      → Balance Invoice → Handover
    - No custom model required — standard Odoo SO Down Payment invoicing used for both invoices
  - Acceptance criteria:
    - `advance_invoice_created` field exists in `helpdesk_ticket` database table
    - Field visible in Extra Info tab, defaults to False
    - Field tracked in chatter log when set to True
    - No custom invoice model created (uses standard Odoo invoicing)
  - Dependencies: Tasks 2.4, 2.5
  - Complexity: XS
  - _Requirements: FR-012_

- [x] 9.6. Add `repair_reason_id` field and mandatory guard (FR-013)
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
    - `jinstage_helpdesk_repair/security/ir.model.access.csv` — verify `jinstage.repair.reason`
      access rows already present from Task 1.4
  - Implementation steps:
    - Add `repair_reason_id = fields.Many2one('jinstage.repair.reason', string='Repair Reason',
      tracking=True)` to `helpdesk.ticket`
    - Add field to Repair Classification group in the Repair Info tab
    - Implement guard in `action_plan_intervention`: if not `self.repair_reason_id`,
      raise `UserError(_('Please set a Repair Reason before planning an intervention.'))`
  - Acceptance criteria:
    - `repair_reason_id` column exists in `helpdesk_ticket` database table
    - Field visible in Repair Info tab Repair Classification group
    - `action_plan_intervention` raises `UserError` when `repair_reason_id` is not set
    - Field tracks changes in chatter
  - Dependencies: Tasks 1.3, 2.3
  - Complexity: S
  - _Requirements: FR-013_

- [x] 9.7. Implement `action_plan_intervention` method (FR-014)
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml` — add Plan Intervention button
  - Implementation steps:
    - Implement `action_plan_intervention(self)`:
      - `ensure_one()`
      - Guard: raise `UserError` if `not self.receive_at_factory`
      - Guard: raise `UserError` if `not self.repair_reason_id`
      - Write: `repair_started_stage_updated = True`
      - Return `self.action_view_fsm_tasks()` (delegates to helpdesk_fsm integration)
    - Add button to form header:
      `<button name="action_plan_intervention" string="Plan Intervention"
               invisible="receive_at_factory == False or repair_started_stage_updated == True"/>`
    - Add `repair_started_stage_updated` to hidden fields in sheet xpath if not already present
  - Acceptance criteria:
    - Button visible when `receive_at_factory = True` and `repair_started_stage_updated = False`
    - Button hidden once `repair_started_stage_updated = True`
    - Method raises `UserError` when either guard fails
    - Method sets `repair_started_stage_updated = True` and returns FSM task action
    - Unit test `test_plan_intervention_success` passes
  - Dependencies: Tasks 4.1, 4.3, 9.6
  - Complexity: S
  - _Requirements: FR-014_

- [x] 9.8. Update integration tests for corrected workflow (all FR changes)
  - Files to modify:
    - `jinstage_helpdesk_repair/tests/test_repair_workflow.py`
    - `jinstage_helpdesk_repair/tests/test_repair_integration.py`
  - Implementation steps:
    - Update `TestRUGWorkflow`: replace `test_factory_blocked_without_approval` with
      `test_factory_no_longer_blocked_by_rug_approval` (factory gate removed)
    - Add `test_rug_request_requires_sale_order` test
    - Add `TestMovementOrder` class with `test_factory_requires_return_transfer` and
      `test_centre_requires_receive_at_factory` tests
    - Add `TestPlanIntervention` class with three test methods (see 8.1 update)
    - Update `test_full_rug_workflow` integration test to use correct order:
      return transfer → factory → plan intervention → RUG request (with SO) → centre
    - Update `test_no_serial_workflow` to verify serial creation succeeds (not raises)
  - Acceptance criteria:
    - All existing tests still pass
    - New tests cover FR-006, FR-007, FR-013, FR-014 corrected behaviour
    - `test_full_rug_workflow` uses factory-first order
    - `test_no_serial_workflow` verifies serial creation is allowed
  - Dependencies: Tasks 9.1 through 9.7, 8.1, 8.2
  - Complexity: M
  - _Requirements: FR-003, FR-005, FR-006, FR-007, FR-012, FR-013, FR-014_

---

## Deployment Checklist

### Pre-Production Deployment
- [ ] All 54 tasks implemented and accepted (32 original + 8 Phase 9 alignment + 14 Phase 10 gap tasks)
- [ ] All unit tests pass (`test_repair_workflow.py`)
- [ ] All integration tests pass (`test_repair_integration.py`)
- [ ] Module installs on clean Odoo 17 Enterprise database
- [ ] No `x_studio_` field references anywhere in the codebase
- [ ] No deprecated API usage (check with `grep -r "attrs=" views/`)
- [ ] All 5 PDF reports generate without error
- [ ] RUG approval workflow tested by helpdesk manager user
- [ ] Cancel/Reopen audit trail verified
- [ ] Repair sequence generating correctly in new tickets
- [ ] Security: helpdesk user cannot access configuration menus

### Post-Installation Configuration
- [ ] Activate company automation rule on helpdesk stages
- [ ] Leave location validation automation rule inactive (activate per-site as needed)
- [ ] Create initial Repair Diagnosis master data (symptom areas, codes, reasons)
- [ ] Create repair-specific helpdesk ticket types (RUG, Normal Serial, Normal No Serial)
- [ ] Configure `users_stock_location` on applicable stock locations
- [ ] Remove Studio customisations from the Helpdesk app after migration verification

---

## Phase 10: FRD Gap Incorporation (14 Gaps)

These tasks close the gaps identified between the Functional Requirement Document and the original
spec. Each task is self-contained and maps 1:1 to a numbered gap.

- [x] 10.1. GAP-01 — Add `customer_type` field (cash/credit) to `helpdesk.ticket`
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
  - Implementation steps:
    - Add `customer_type = fields.Selection([('cash', 'Cash'), ('credit', 'Credit')],
      string='Customer Type', default='cash', tracking=True)` to `helpdesk.ticket`
    - Add field to Repair Info tab (Repair Classification group)
    - Document business rules: cash = 50% advance + 100% final; credit = credit limit check first
  - Acceptance criteria:
    - `customer_type` defaults to `'cash'` on new tickets
    - Field appears in Repair Info tab
    - Field tracked in chatter when changed
  - Dependencies: Task 2.3
  - Complexity: XS
  - _Requirements: FR-NEW-01_

- [x] 10.2. GAP-02 — Credit limit validation workflow
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
  - Implementation steps:
    - Add `credit_limit_request_sent` and `credit_limit_approved` boolean fields
    - Implement `action_request_credit_limit` method with guards and chatter post
    - Add "Request Credit Limit" button to form header:
      `invisible="customer_type != 'credit' or credit_limit_request_sent == True"`
    - Add fields to Extra Info tab under Workflow Status group
  - Acceptance criteria:
    - `action_request_credit_limit` raises `UserError` for non-credit customers
    - `action_request_credit_limit` raises `UserError` if already sent
    - Chatter message posted on request
    - Button visible only for credit customers who have not yet sent the request
  - Dependencies: Tasks 2.4, 10.1
  - Complexity: S
  - _Requirements: FR-NEW-02_

- [x] 10.3. GAP-03 — Quotation 25-day expiry computed field
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
  - Implementation steps:
    - Add `quotation_expiry_date = fields.Date(compute='_compute_quotation_expiry_date', store=True)`
    - Implement `_compute_quotation_expiry_date` with `@api.depends('sale_order',
      'sale_order.create_date')` — SO creation date + 25 days
    - Display `quotation_expiry_date` in Extra Info tab (Sale Order Flags group)
    - Add guard in quotation confirmation logic: if `quotation_expiry_date < date.today()`,
      raise `UserError`
    - Add automation rule comment in `automation_rules.xml` noting expiry is computed not ruled
  - Acceptance criteria:
    - `quotation_expiry_date` populated 25 days after SO creation
    - `quotation_expiry_date` is False when no `sale_order`
    - Guard raises `UserError` when today exceeds `quotation_expiry_date`
    - Field recomputes when `sale_order` changes
  - Dependencies: Tasks 2.5, 4.3
  - Complexity: S
  - _Requirements: FR-NEW-03_

- [x] 10.4. GAP-04 — Insufficient inventory computed boolean block
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
  - Implementation steps:
    - Add `insufficient_inventory = fields.Boolean(compute='_compute_insufficient_inventory',
      store=False)`
    - Implement `_compute_insufficient_inventory` with `@api.depends('items',
      'repair_location')` — searches `stock.quant` for each product in `items` at
      `repair_location`; True if any product quantity <= 0
    - Add warning message in form view visible when `insufficient_inventory == True`:
      `<div class="alert alert-warning" invisible="insufficient_inventory == False">`
    - Add `insufficient_inventory` to hidden fields xpath for domain expressions
  - Acceptance criteria:
    - `insufficient_inventory = True` when any item has qty <= 0 in repair location
    - `insufficient_inventory = False` when `items` is empty or all items have stock
    - Warning banner visible in form when `insufficient_inventory = True`
    - Quotation confirmation action blocks when `insufficient_inventory = True`
  - Dependencies: Tasks 2.5, 4.2
  - Complexity: M
  - _Requirements: FR-NEW-04_

- [x] 10.5. GAP-05 — "Tested OK" workflow
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
  - Implementation steps:
    - Add `tested_ok = fields.Boolean(string='Tested OK', default=False, tracking=True)`
    - Implement `action_tested_ok` method:
      - Guards: `receive_at_factory` must be True; `fsm_task_done` must be False
      - Sets `tested_ok = True`, moves ticket to "Repair Completed" stage
    - Add "Tested OK" button to form header:
      `invisible="tested_ok == True or receive_at_factory == False or fsm_task_done == True"`
    - Update `action_dispatch` to skip payment gate when `tested_ok = True`
    - Add `tested_ok` to hidden fields xpath
  - Acceptance criteria:
    - `action_tested_ok` raises `UserError` if `receive_at_factory = False`
    - `action_tested_ok` raises `UserError` if `fsm_task_done = True`
    - Ticket moves to "Repair Completed" stage on success
    - Dispatch available immediately after `tested_ok = True`
  - Dependencies: Tasks 2.4, 4.1, 10.12 (GAP-12 stages must exist)
  - Complexity: S
  - _Requirements: FR-NEW-05_

- [x] 10.6. GAP-06 — Mandatory image upload and diagnosis validation
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
  - Implementation steps:
    - Add `image_uploaded = fields.Boolean(compute='_compute_image_uploaded', store=True)`
    - Implement `_compute_image_uploaded` with `@api.depends('related_information',
      'warranty_card')` — True when either field has a value
    - Add `diagnosis_validated = fields.Boolean(string='Diagnosis Validated',
      default=False, tracking=True)`
    - Update `action_plan_intervention`: add guard `if not self.image_uploaded: raise UserError`
    - Add both fields to Repair Info tab
    - Add `diagnosis_validated` check comment in FSM task product-add path
  - Acceptance criteria:
    - `image_uploaded = True` when `warranty_card` or `related_information` is populated
    - `image_uploaded = False` when both fields are empty
    - `action_plan_intervention` raises `UserError` when `image_uploaded = False`
    - `diagnosis_validated` visible in Repair Info tab and tracked in chatter
  - Dependencies: Tasks 2.5, 9.7
  - Complexity: S
  - _Requirements: FR-NEW-06_

- [x] 10.7. GAP-07 — `action_dispatch` with payment gate
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
  - Implementation steps:
    - Add `dispatch_done = fields.Boolean(string='Dispatched', readonly=True,
      default=False, tracking=True)`
    - Implement `action_dispatch` method with guards:
      - Cash: `valid_invoiced_so` must be True (unless `tested_ok = True`)
      - Credit: `credit_limit_approved` must be True (unless `tested_ok = True`)
      - RUG: `rug_approved` must be True
      - Sets `handed_over = True`, `dispatch_done = True`
      - Creates stock Return Operation picking from `repair_location` → customer location
    - Add "Dispatch" button to form header:
      `invisible="dispatch_done == True or (receive_at_centre == False and tested_ok == False)"`
    - Add `dispatch_done` to Extra Info tab (readonly)
  - Acceptance criteria:
    - Cash customer dispatch blocked when `valid_invoiced_so = False` and `tested_ok = False`
    - Credit customer dispatch blocked when `credit_limit_approved = False` and `tested_ok = False`
    - `tested_ok = True` bypasses payment gate
    - `handed_over = True` and `dispatch_done = True` set atomically
    - Stock Return Operation picking created and linked to ticket
  - Dependencies: Tasks 2.4, 3.5, 10.1, 10.2, 10.5
  - Complexity: M
  - _Requirements: FR-NEW-07_

- [x] 10.8. GAP-08 — RUG rejection repricing chatter and `rug_repriced` field
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
  - Implementation steps:
    - Add `rug_repriced = fields.Boolean(string='RUG Repriced', default=False, tracking=True)`
    - Update `action_reject_rug`:
      - Write `rug_repriced = False` (flag that repricing has not been done)
      - Post chatter message: "RUG approval rejected. Pricing must be updated to standard repair
        rates before the repair can proceed. Please revise the quotation accordingly."
    - Add `rug_repriced` to Extra Info tab (RUG Approval group), readonly until manager sets True
  - Acceptance criteria:
    - `action_reject_rug` posts chatter message on rejection
    - `rug_repriced = False` set when rejection occurs
    - Manager can manually set `rug_repriced = True` after repricing the quotation
    - Chatter message visible in ticket audit trail
  - Dependencies: Task 3.4
  - Complexity: XS
  - _Requirements: FR-007 (GAP-08)_

- [x] 10.9. GAP-09 — RUG account on ticket type + dispatch gate for RUG
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket_type.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_type_views.xml`
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py` — update `action_dispatch`
  - Implementation steps:
    - Add `rug_account_id = fields.Many2one('account.account', string='RUG Account',
      help='GL account for final RUG repair invoices.')` to `helpdesk.ticket.type`
    - Add `rug_account_id` to the ticket type form/tree views
    - In `action_dispatch`: add guard for RUG tickets —
      `if self.rug_confirmed and not self.rug_approved: raise UserError`
    - Add note in code: RUG invoices should be posted against `ticket_type_id.rug_account_id`
  - Acceptance criteria:
    - `helpdesk.ticket.type` has `rug_account_id` Many2one field
    - Ticket type form shows `rug_account_id` field (only relevant for RUG types)
    - `action_dispatch` blocks for RUG tickets when `rug_approved = False`
    - `action_dispatch` blocks for RUG tickets when `valid_invoiced_so = False`
  - Dependencies: Tasks 2.1, 3.4, 10.7
  - Complexity: S
  - _Requirements: FR-NEW (GAP-09)_

- [x] 10.10. GAP-10 — Temporary serial sequence for "Without Serial No" type
  - Files to modify:
    - `jinstage_helpdesk_repair/data/ir_sequence_data.xml`
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
  - Implementation steps:
    - Add `repair.temp.serial` sequence to `ir_sequence_data.xml`:
      prefix `REP/SER/%(year)s/`, padding 3
    - Update `action_create_serial_number`: when `normal_repair_without_serial_no = True`,
      use `env['ir.sequence'].next_by_code('repair.temp.serial')` as the lot name instead of
      `self.name`
    - All other types continue to use `self.name` as the lot name
  - Acceptance criteria:
    - `repair.temp.serial` sequence exists in database after install
    - `action_create_serial_number` for "Without Serial No" type generates lot name from temp
      serial sequence (e.g. `REP/SER/2026/001`)
    - All other types continue to use ticket reference as lot name
    - Sequence increments correctly on each call
  - Dependencies: Tasks 1.2, 3.2
  - Complexity: S
  - _Requirements: FR-003 (GAP-10)_

- [x] 10.11. GAP-11 — Customer-declined cancel → "Repair Completed" stage (not cancelled)
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py`
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml`
  - Implementation steps:
    - Add `'customer_declined'` to `cancel_status` selection values:
      `('customer_declined', 'Customer Declined Quotation')`
    - Update `action_cancel_ticket`: when `cancel_status == 'customer_declined'`:
      - Do NOT set `cancelled = True`
      - Move ticket to "Repair Completed" stage
      - Post chatter: "Customer declined quotation. Ticket moved to Repair Completed.
        Intervention Task must be marked Done manually. Item returned via Sales Centre dispatch."
    - Standard cancel path (all other reasons) unchanged
  - Acceptance criteria:
    - `action_cancel_ticket` with `cancel_status = 'customer_declined'` moves to
      "Repair Completed" stage (not cancelled)
    - `cancelled` field remains False for customer-declined tickets
    - Chatter message posted for customer-declined path
    - All other cancel reasons continue to set `cancelled = True`
  - Dependencies: Tasks 3.3, 10.12
  - Complexity: S
  - _Requirements: FR-008 (GAP-11)_

- [x] 10.12. GAP-12 — Seed 13 repair stages in `data/repair_stages.xml`
  - Files to create:
    - `jinstage_helpdesk_repair/data/repair_stages.xml`
  - Files to modify:
    - `jinstage_helpdesk_repair/__manifest__.py` — add `data/repair_stages.xml` after
      `ir_sequence_data.xml` in `data` list
  - Implementation steps:
    - Create 13 `helpdesk.stage` records with sequences 10–130:
      1. New (seq 10), 2. Item Received (20), 3. Sent to Factory (30),
      4. Received at Factory (40), 5. Repair Started (50), 6. Quotation (60),
      7. Quotation Sent to Customer (70), 8. SO Confirmed (80), 9. Repair Completed (90),
      10. Sent to Sales Centre (100), 11. Received at Sales Centre (110),
      12. Dispatched (120), 13. Handed Over to Customer (130, `is_close=True`)
    - All stages have no `company_id` on install (global)
    - Use `noupdate="1"` to prevent re-seeding on module upgrade
  - Acceptance criteria:
    - 13 stage records exist after module installation
    - "Handed Over to Customer" has `is_close = True`
    - Stages appear in correct sequence order in the Kanban pipeline
    - `noupdate="1"` prevents overwriting admin-customised stages on upgrade
  - Dependencies: Task 2.2
  - Complexity: S
  - _Requirements: FR-NEW-08 (GAP-12)_

- [x] 10.13. GAP-13 — Document multiple delivery orders for factory repairs
  - Files to modify:
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py` — add comment block
    - `jinstage_helpdesk_repair/views/helpdesk_ticket_views.xml` — verify smart button label
  - Implementation steps:
    - Add comment block in `_compute_picking_ids` documenting the multi-DO pattern:
      - Branch repairs: 1 DO (branch → customer)
      - Centre/Factory repairs: 3+ DOs (branch → factory, factory → centre, centre → customer)
    - Confirm "Repair Trans" smart button shows total count of all linked DOs
    - No additional model changes required — existing `picking_count` covers all legs
    - Add `picking_count` note to design doc (already done via spec update)
  - Acceptance criteria:
    - `picking_count` smart button shows the correct total count for multi-DO factory repairs
    - Comment block in code explains the multi-DO pattern
    - No new model changes required — existing `helpdesk_ticket_id` link handles all DOs
  - Dependencies: Task 3.5
  - Complexity: XS
  - _Requirements: FR-005 / FR-006 (GAP-13)_

- [x] 10.14. GAP-14 — `jinstage.repair.bom` model for repair BOMs
  - Files to create:
    - `jinstage_helpdesk_repair/models/repair_bom.py`
  - Files to modify:
    - `jinstage_helpdesk_repair/models/__init__.py` — add import for `repair_bom`
    - `jinstage_helpdesk_repair/security/ir.model.access.csv` — add 2 rows for
      `model_jinstage_repair_bom`
    - `jinstage_helpdesk_repair/views/diagnosis_views.xml` — add BOM list + form views
    - `jinstage_helpdesk_repair/views/actions.xml` — add `action_repair_bom` act_window
    - `jinstage_helpdesk_repair/views/menus.xml` — add BOM submenu under Repair Diagnosis
    - `jinstage_helpdesk_repair/models/helpdesk_ticket.py` — add `action_apply_bom` method
  - Implementation steps:
    - Create `jinstage.repair.bom` model with `name`, `repair_type_id`, `product_ids`,
      `active` fields (see design.md section 7)
    - `product_ids` uses explicit relation `jinstage_repair_bom_product_rel`
    - Implement `action_apply_bom(self, bom_id)` on `helpdesk.ticket`: appends BOM products
      to `items` field (does not replace existing entries)
    - List view: `name`, `repair_type_id`, `product_ids` (as tag list), `active`
    - Form view: `name`, `repair_type_id`, `product_ids` (as list widget), `active`
    - Menu: under `menu_repair_diagnosis_root` as "Repair BOMs", sequence 95
    - Security: user group read-only; manager group full access
  - Acceptance criteria:
    - `jinstage.repair.bom` model exists in database after install
    - BOM form view allows adding multiple products
    - `action_apply_bom` appends products to ticket `items` (not replaces)
    - BOM accessible under Helpdesk > Configuration > Repair Diagnosis > Repair BOMs
    - Manager-only create/write/delete; users can read
  - Dependencies: Tasks 1.3, 1.4, 2.5
  - Complexity: M
  - _Requirements: FR-NEW-09 (GAP-14)_

---

**Last Updated:** 2026-04-08
**Document Version:** 1.0
**Approval Status:** Draft
