# Odoo Module Requirements Document - jinstage_helpdesk_repair

## Module Overview

**Module Name:** jinstage_helpdesk_repair
**Odoo Version:** 17.0 (Enterprise)
**Module Version:** 1.0.0
**Developer:** Jinasena Pvt Ltd
**Category:** Helpdesk / Repair Management
**Technical Name:** jinstage_helpdesk_repair
**Depends:** helpdesk, helpdesk_fsm, helpdesk_sale, industry_fsm, stock, sale_management, account, product

---

## Business Requirements Alignment

### Business Process Impact

The `jinstage_helpdesk_repair` module transforms Odoo's standard helpdesk ticketing system into a
comprehensive Repair Management System. It migrates all Studio-based customisations into a proper,
maintainable Python/XML module, providing a full repair lifecycle: intake, routing, centre/factory
movement, serial number tracking, RUG (special category) approval, invoicing, and job handover.

The module handles four distinct repair types across two warranty categories — Under Warranty (RUG
and External not RUG) and Not Under Warranty (With Serial Number and Without Serial Number) — each
with its own workflow constraints, location routing rules, and document requirements. The
distinguishing flag between the two Under Warranty subtypes is `rug_confirmed`: full internal
approval applies only when both `rug_repair = True` and `rug_confirmed = True`.

### ROI Assessment

- **Expected Benefits:** Elimination of Studio customisation fragility, traceable repair lifecycles,
  automated sequence numbering, enforced RUG approval, complete audit trail for cancellations and
  reopens, and location-based access control.
- **Implementation Cost:** Estimated 8-phase development (32 atomic tasks), approximately 160–240
  developer hours.
- **Payback Period:** Operational savings in manual tracking and rework expected within 3 months of
  go-live.

---

## Functional Requirements

### FR-001 — Automatic Repair Sequence Number

**Priority:** High

**User Story:** As a helpdesk agent, I want each new repair ticket to receive a unique reference
number automatically, so that I can identify and track repairs without manual numbering.

#### Acceptance Criteria
1. When a helpdesk ticket is created and `name` equals `'New'`, the system assigns the next value
   from ir.sequence code `repair.seq`.
2. The generated reference follows the format `REP/YYYY/NNNNN` (configurable prefix and padding).
3. Sequence assignment is idempotent — re-saving a ticket already assigned a number does not change
   the number.
4. The automation rule (on_create_or_write) triggers sequence assignment server-side, not in the
   ORM `create` method, matching the existing Studio automation behaviour.

#### Business Rules
- Sequence code: `repair.seq`
- The automation rule is active and fires on create or write when `name = 'New'`.
- Sequence must be unique across the database (no duplicate repair references).

#### Data Requirements
```python
# ir.sequence record
{
    'name': 'Repair Sequence',
    'code': 'repair.seq',
    'prefix': 'REP/%(year)s/',
    'padding': 5,
    'number_increment': 1,
    'use_date_range': False,
}
```

---

### FR-002 — Four Repair Type Classification

**Priority:** High

**User Story:** As a service manager, I want to classify every repair ticket into one of four types
(Under Warranty — RUG, Under Warranty — External not RUG, Not Under Warranty With Serial, Not Under
Warranty Without Serial), so that the correct workflow and form fields are presented automatically.

#### Acceptance Criteria
1. `helpdesk.ticket.type` gains four boolean flags: `is_rug`, `is_rug_confirmed`,
   `is_with_serial_no`, and `is_without_serial_no`.
2. On the helpdesk ticket, four related boolean fields mirror the ticket type's flags:
   `rug_repair`, `rug_confirmed`, `normal_repair_with_serial_no`, `normal_repair_without_serial_no`.
3. Form view renders conditional field groups and buttons depending on these related booleans.
4. Each of the four ticket type records has exactly one (or two for RUG) flags set to True,
   matching the matrix below.

#### Business Rules
The four ticket type records and their flag combinations:

| Ticket Type Name | is_rug | is_rug_confirmed | is_with_serial_no | is_without_serial_no |
|---|---|---|---|---|
| Repair - Under Warranty - RUG | ✓ | ✓ | — | — |
| Repair - Under Warranty - External not RUG | ✓ | — | — | — |
| Repair - Not Under Warranty (With Serial No) | — | — | ✓ | — |
| Repair - Not Under Warranty (Without Serial No) | — | — | — | ✓ |

- `rug_repair` (related to `ticket_type_id.is_rug`) is True for BOTH Under Warranty types.
  It activates RUG-specific buttons ("Request RUG Approval", "Approve RUG").
- `rug_confirmed` (related to `ticket_type_id.is_rug_confirmed`) is True ONLY for the
  "Under Warranty - RUG" type. It is the distinguishing flag that gates the full internal
  approval workflow and controls visibility of RUG Approval Status on the kanban card.
- These related fields are stored (`store=True`) to support efficient domain filtering.

#### Data Requirements
```python
# helpdesk.ticket.type additional fields (4 flags)
{
    'is_rug': fields.Boolean(string='RUG', default=False),
    'is_rug_confirmed': fields.Boolean(string='RUG Confirmed', default=False),
    'is_with_serial_no': fields.Boolean(string='With Serial Number', default=False),
    'is_without_serial_no': fields.Boolean(string='Without Serial Number', default=False),
}

# helpdesk.ticket — related fields mirroring ticket type flags
{
    'rug_repair': fields.Boolean(related='ticket_type_id.is_rug', store=True),
    'rug_confirmed': fields.Boolean(related='ticket_type_id.is_rug_confirmed', store=True),
    'normal_repair_with_serial_no': fields.Boolean(
        related='ticket_type_id.is_with_serial_no', store=True),
    'normal_repair_without_serial_no': fields.Boolean(
        related='ticket_type_id.is_without_serial_no', store=True),
}
```

---

### FR-003 — Serial Number Create and Link for Serial-Tracked Repairs

**Priority:** High

**User Story:** As a technician, I want to create or link a stock serial number (lot) to a repair
ticket, so that the repaired item is traceable throughout the repair process.

#### Acceptance Criteria
1. Field `repair_serial_no` (Many2one to `stock.lot`) appears on the ticket when
   `normal_repair_with_serial_no = True` or `rug_repair = True`.
2. A `Create Serial Number` button is available when `repair_serial_created = False` and the repair
   type requires a serial.
3. Clicking the button creates a new `stock.lot` record and links it to the ticket, setting
   `repair_serial_created = True`.
4. Field `sn_updated` is set to True when an existing serial number is updated on the ticket.
5. A legacy `serial_number` field (Many2one to `stock.lot`) is retained for backward compatibility
   with existing data.
6. For "Without Serial No" type (`normal_repair_without_serial_no = True`), the system MAY create
   an internal reference serial number when the user explicitly requests it. The serial is used for
   internal tracking only and does not surface as a mandatory step.

#### Business Rules
- Serial creation is available for all repair types, including "Without Serial No".
  For the "Without Serial No" type, the created serial serves as an internal reference.
- The previous restriction blocking `action_create_serial_number` for `normal_repair_without_serial_no`
  type is removed. The button may be shown for all types at the discretion of the form view.
- One ticket maps to one serial number (the repaired unit).
- Serial creation must associate the lot with the correct product from the ticket.

#### Data Requirements
```python
{
    'repair_serial_no': fields.Many2one('stock.lot', string='Serial Number',
                                        tracking=True),
    'serial_number': fields.Many2one('stock.lot', string='Serial Number (Legacy)'),
    'repair_serial_created': fields.Boolean(string='Serial Created', default=False),
    'sn_updated': fields.Boolean(string='SN Updated', default=False),
}
```

---

### FR-004 — Four Location Fields Assignment

**Priority:** High

**User Story:** As a service coordinator, I want to assign specific stock locations for each stage of
the repair journey, so that stock movements are created to the correct warehouses and locations.

#### Acceptance Criteria
1. Four `stock.location` Many2one fields appear on the ticket:
   - `repair_location` — where the repair is performed
   - `return_receipt_location` — where the item is received back from the customer
   - `source_location` — origin location for the route
   - `job_location` — on-site job location for FSM tasks
2. All four fields appear in the Extra Info tab of the ticket form.
3. Location fields are optional on ticket creation but may be mandatory at specific workflow stages
   (enforced by stage-based validation).

#### Business Rules
- Location fields link to `stock.location` records with `usage` in `['internal', 'customer',
  'transit']`.
- `user_location_validation` computed boolean checks whether the current user is permitted to access
  the assigned locations (see FR-009).

#### Data Requirements
```python
{
    'repair_location': fields.Many2one('stock.location', string='Repair Location'),
    'return_receipt_location': fields.Many2one('stock.location',
                                               string='Return Receipt Location'),
    'source_location': fields.Many2one('stock.location', string='Source Location'),
    'job_location': fields.Many2one('stock.location', string='Job Location'),
}
```

---

### FR-005 — Create Return Transfer (Stock Picking Records)

**Priority:** High

**User Story:** As a service manager, I want to generate a return transfer stock picking for a
repair ticket with one click, so that the defective item is received into the repair location
automatically without manual data entry.

#### Acceptance Criteria
1. A `Create Return Transfer` button (previously labelled "Create Repair Route") on the ticket
   form triggers a reverse transfer (return picking) that receives the defective item into the
   repair location.
2. A popup dialog allows the user to confirm the return location before the transfer is created.
3. Each generated picking includes a reverse Many2one back-reference to the originating
   `helpdesk.ticket`.
4. A `picking_id` Many2one field on `helpdesk.ticket` references the primary inbound picking.
5. The smart button "Repair Trans" (previously "Pickings") on the ticket header shows the count of
   linked pickings and opens the filtered list.
6. `stock.picking` gains a `helpdesk_ticket_id` Many2one field linking back to `helpdesk.ticket`.

#### Business Rules
- Return transfer creation is only available when required location fields are set.
- The return transfer is a reverse (return) picking that moves the item from the customer/source
  location into the repair location.
- Picking type and location are determined by the ticket's location fields and repair type.

#### Data Requirements
```python
# helpdesk.ticket
{
    'picking_id': fields.Many2one('stock.picking', string='Receipt',
                                  tracking=True),
    'picking_ids': fields.Many2many('stock.picking',
                                    compute='_compute_picking_ids',
                                    string='Pickings'),
    'picking_count': fields.Integer(compute='_compute_picking_ids'),
}

# stock.picking extension
{
    'helpdesk_ticket_id': fields.Many2one('helpdesk.ticket',
                                          string='Repair Ticket'),
}
```

---

### FR-006 — Factory and Sales Centre Transfer Tracking

**Priority:** High

**User Story:** As a logistics coordinator, I want to track whether a repair item has been sent to
the factory for repair and then dispatched to the sales centre for customer collection, so that I
know the physical location of every item in the repair pipeline.

#### Acceptance Criteria
1. Four boolean checkpoint fields exist: `send_to_factory`, `receive_at_factory`,
   `send_to_centre`, `receive_at_centre`.
2. Each flag is set via a dedicated action button or toggled from the form.
3. User tracking fields (`s_received_by`, `f_received_by`, `s_shipped_by`, `f_shipped_by`) record
   the `res.users` responsible for each movement event.
4. `stage_date` datetime is updated when a stage-changing event occurs.

#### Business Rules

**Correct movement order (factory FIRST, then sales centre AFTER repair):**
```
Create Return Transfer → Send to Factory → Receive at Factory
    → [Repair Work] → Send to Sales Centre → Receive at Sales Centre → Handover
```

- `action_send_to_factory`: requires only `picking_count > 0` (return transfer must exist).
  There is NO centre prerequisite — the item goes directly to the factory after intake.
- `send_to_factory` must be True before `receive_at_factory` can be set.
- `action_send_to_centre`: requires `receive_at_factory = True` (repair at factory must be
  complete before the item is dispatched to the sales centre for handover).
- `send_to_centre` must be True before `receive_at_centre` can be set.
- User tracking fields are set automatically to the current user when the flag is toggled.

#### Data Requirements
```python
{
    'send_to_centre': fields.Boolean(string='Send to Centre', tracking=True),
    'receive_at_centre': fields.Boolean(string='Received at Centre', tracking=True),
    'send_to_factory': fields.Boolean(string='Send to Factory', tracking=True),
    'receive_at_factory': fields.Boolean(string='Received at Factory', tracking=True),
    's_received_by': fields.Many2one('res.users', string='Received by (Centre)'),
    'f_received_by': fields.Many2one('res.users', string='Received by (Factory)'),
    's_shipped_by': fields.Many2one('res.users', string='Shipped by (Centre)'),
    'f_shipped_by': fields.Many2one('res.users', string='Shipped by (Factory)'),
    'stage_date': fields.Datetime(string='Stage Date', tracking=True),
}
```

---

### FR-007 — RUG Approval Workflow

**Priority:** High

**User Story:** As a service manager, I want "Under Warranty — RUG" repairs to go through an
internal approval workflow before factory work begins, so that high-value warranty repairs are
authorised at the correct level. "Under Warranty — External not RUG" repairs must NOT require
this approval step.

#### Acceptance Criteria
1. When `rug_repair = True` AND `rug_confirmed = True` (i.e. type is "Under Warranty - RUG"),
   a `Send RUG Request` button is available on the form.
2. `action_send_rug_request` requires that a Sale Order (quotation) already exists on the ticket
   (`sale_order` must be set). The RUG approval request is raised AFTER the quotation is created
   and BEFORE the customer confirms the SO.
3. Clicking the button sets `rug_request_sent = True` and `rug_approval_status = 'pending'`.
4. An approver can set `rug_approval_status` to `'approved'` or `'rejected'`.
5. When approved: `rug_approved = True` and the customer may then confirm the SO.
6. When rejected: the ticket is blocked from SO confirmation and status shows `'rejected'`.
7. When `rug_repair = True` BUT `rug_confirmed = False` (i.e. type is "Under Warranty — External
   not RUG"), the approval buttons are NOT shown and no approval is required. The ticket proceeds
   directly after intake and location setup.
8. `rug_approval_status` selection values: `pending`, `approved`, `rejected`.

#### Business Rules

**RUG Approval position in workflow (timing change):**
```
Plan Intervention → Add Products to FSM Task → Quotation (SO) Created
    → Request RUG Approval → [Manager Approves] → Customer Confirms SO
    → 50% Advance Invoice → Repair Work → Balance Invoice → Handover
```

- Full internal RUG approval (`Send RUG Request` → approve/reject) applies ONLY when
  `rug_repair = True AND rug_confirmed = True`.
- `action_send_rug_request` guards: raise `UserError` if `sale_order` is not set (quotation
  must exist before the RUG request can be submitted).
- The factory gate (`action_send_to_factory`) no longer blocks on RUG approval status.
  The approval now gates SO confirmation, not factory dispatch.
- "Under Warranty — External not RUG" tickets (`rug_repair = True, rug_confirmed = False`)
  share the `rug_repair` flag but bypass the approval step entirely.
- Only users in the helpdesk manager group can approve or reject.

#### Data Requirements
```python
{
    'rug_approval_status': fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='RUG Approval Status', tracking=True),
    'rug_request_sent': fields.Boolean(string='RUG Request Sent', default=False,
                                        tracking=True),
    'rug_approved': fields.Boolean(string='RUG Approved', default=False,
                                   tracking=True),
    # Note: rug_confirmed on the ticket is a related field from ticket_type_id.is_rug_confirmed
    # (see FR-002). rug_approved is the workflow flag set during the approval process.
}
```

---

### FR-008 — Cancel and Reopen Audit Trail

**Priority:** High

**User Story:** As a compliance officer, I want every cancellation and reopening of a repair ticket
to be fully audited with user, timestamp, and stage snapshot, so that I can trace why and when
tickets changed state.

#### Acceptance Criteria
1. A `Cancel` action button opens a reason selection and sets `cancelled = True`,
   `cancelled_date = now()`, `cancelled_by = env.user`, and `cancelled_stage_id` to the current
   stage.
2. A `Reopen` button restores the ticket, sets `reopened_date = now()`, `reopened_by = env.user`,
   and `reopen_status`.
3. The `Cancel/Reopen Log` tab on the form view displays the full audit fields.
4. `cancel_status` selection tracks the reason for cancellation.
5. `re_estimate_status` and `reopen_status` selections track re-estimation and reopen reasons.

#### Business Rules
- Only active (non-cancelled) tickets can be cancelled.
- Only cancelled tickets can be reopened.
- All audit fields are readonly after being set.
- `cancelled_2` is a secondary cancel flag for two-stage cancellation scenarios.

#### Data Requirements
```python
{
    'cancelled': fields.Boolean(string='Cancelled', default=False, tracking=True),
    'cancelled_2': fields.Boolean(string='Cancelled (Stage 2)', default=False),
    'cancelled_date': fields.Datetime(string='Cancelled Date'),
    'cancelled_by': fields.Many2one('res.users', string='Cancelled By'),
    'cancelled_stage_id': fields.Many2one('helpdesk.stage',
                                          string='Stage at Cancellation'),
    'reopened_date': fields.Datetime(string='Reopened Date'),
    'reopened_by': fields.Many2one('res.users', string='Reopened By'),
    'cancel_status': fields.Selection([...], string='Cancellation Reason'),
    'reopen_status': fields.Selection([...], string='Reopen Reason'),
    're_estimate_status': fields.Selection([...], string='Re-Estimate Status'),
}
```

---

### FR-009 — User Location Validation

**Priority:** Medium

**User Story:** As a security administrator, I want to restrict certain repair operations to users
who are authorised for the repair's assigned location, so that only the right personnel can process
repairs at each location.

#### Acceptance Criteria
1. `stock.location` gains a `users_stock_location` Many2many field to `res.users` listing permitted
   users.
2. `user_location_validation` on `helpdesk.ticket` is a computed readonly boolean that is True when
   `env.user` is in the permitted users list of the ticket's `repair_location`.
3. Action buttons that require location permission are conditionally hidden when
   `user_location_validation = False`.
4. An inactive automation rule (location_validation_rule) can be activated to enforce server-side
   validation on stage change.

#### Business Rules
- An empty `users_stock_location` list means all users are permitted (no restriction).
- Validation runs on `repair_location` field specifically.
- The computed field is not stored (realtime evaluation per user context).

#### Data Requirements
```python
# stock.location extension
{
    'users_stock_location': fields.Many2many('res.users',
                                              string='Permitted Users'),
}

# helpdesk.ticket
{
    'user_location_validation': fields.Boolean(
        string='Location Access Valid',
        compute='_compute_user_location_validation',
        store=False,
    ),
}
```

---

### FR-010 — Multi-Company Stage Scoping

**Priority:** Medium

**User Story:** As a system administrator in a multi-company deployment, I want helpdesk stages to
be scoped to the active company, so that different companies can maintain separate repair stage
configurations.

#### Acceptance Criteria
1. `helpdesk.stage` gains a `company_id` Many2one field to `res.company`.
2. An active automation rule fires on `helpdesk.stage` create/write and sets `company_id` from
   the `allowed_company_ids` context.
3. Stage records without a `company_id` are visible to all companies (global stages).
4. The stage form and tree views display the `company_id` field.

#### Business Rules
- Company assignment uses `env.context.get('allowed_company_ids', [env.user.company_id.id])[0]`.
- The automation rule code: sets `record['company_id']` from the resolved company.

#### Data Requirements
```python
# helpdesk.stage extension
{
    'company_id': fields.Many2one('res.company', string='Company',
                                  tracking=True),
}
```

---

### FR-011 — Warranty Card and Document Storage

**Priority:** Medium

**User Story:** As a service agent, I want to attach a warranty card image and related repair
documents directly on the ticket, so that all documentation is accessible without navigating to
a separate attachment view.

#### Acceptance Criteria
1. `warranty_card` field (Binary/Image widget) appears in the main tab of the repair form.
2. `related_information` field (Binary/Image widget) stores supplementary documents.
3. Both fields are displayed inline in the form view using the `image` widget or file upload widget.
4. Documents are stored in the database (attachment-linked or direct binary).

#### Business Rules
- Maximum image size: 10 MB per field.
- Supported formats: JPG, PNG, PDF (displayed as image or download link).
- Fields are optional and visible to all repair team members.

#### Data Requirements
```python
{
    'warranty_card': fields.Binary(string='Warranty Card',
                                   attachment=True),
    'related_information': fields.Binary(string='Related Information',
                                         attachment=True),
}
```

---

### FR-012 — 50% Advance Payment and Two-Invoice Workflow

**Priority:** High

**User Story:** As a service accountant, I want a 50% advance invoice created after the customer
confirms the SO, and a remaining balance invoice after repair completion, so that the repair job
is financially tracked across two invoicing events.

#### Acceptance Criteria
1. After the customer confirms the Sale Order (Step 11 in the end-user workflow), a 50% advance
   invoice is created using standard Odoo SO invoicing (Down Payment type).
2. The boolean flag `advance_invoice_created` is set to True when the advance invoice has been
   created.
3. Repair work begins only after the advance payment is confirmed.
4. After repair completion (FSM task done), the remaining balance invoice is created from the SO.
5. `balance_due` (Float) tracks the remaining outstanding amount after the advance is applied.
6. `sale_order` computed field (Many2one to `sale.order`) extracts the related SO from FSM tasks.
7. Smart buttons for Sales Orders and Invoices show counts and link to filtered views.

#### Business Rules

**Two-invoice workflow:**
```
Customer Confirms SO → 50% Advance Invoice Created (advance_invoice_created = True)
    → Advance Payment Received → Repair Work Begins
    → Repair Completed → Remaining Balance Invoice Created
    → Balance Payment Received → Handover
```

- No custom model is required — standard Odoo SO Down Payment invoicing is used for both invoices.
- `advance_invoice_created` boolean flag on `helpdesk.ticket` tracks whether the advance invoice
  has been raised.
- Sale order lifecycle flags `valid_confirmed_so`, `valid_confirmed2_so`, `valid_delivered_so`,
  `valid_invoiced_so` reflect the linked SO state milestones.
- `invoice_stage_updated` boolean flag indicates the ticket stage was updated on invoicing.

#### Data Requirements
```python
{
    'advance_invoice_created': fields.Boolean(
        string='Advance Invoice Created', default=False, tracking=True
    ),
    'balance_due': fields.Float(string='Balance Due', tracking=True),
    'sales_price': fields.Char(string='Sales Price'),
    'unit_price': fields.Float(string='Unit Price'),
    'quantity': fields.Integer(string='Quantity', default=1),
    'qty': fields.Char(string='Qty'),
    'items': fields.Many2many('product.product', string='Items'),
    'sale_order': fields.Many2one('sale.order', string='Sale Order',
                                  compute='_compute_sale_order', store=True),
    'valid_confirmed_so': fields.Boolean(string='SO Confirmed'),
    'valid_confirmed2_so': fields.Boolean(string='SO Confirmed (2)'),
    'valid_delivered_so': fields.Boolean(string='SO Delivered'),
    'valid_invoiced_so': fields.Boolean(string='SO Invoiced'),
    'invoice_stage_updated': fields.Boolean(string='Invoice Stage Updated'),
}
```

---

### FR-012b — General Financial Tracking Fields

**Priority:** Medium

**User Story:** As a service accountant, I want financial data including balance due, pricing
information, and sale order lifecycle flags on the repair ticket, so that I can monitor repair
revenue and invoice status without switching to the accounting module.

#### Acceptance Criteria
1. `balance_due` (Float) tracks the outstanding amount for the repair.
2. `sales_price` (Char) and `unit_price` (Float) store pricing information.
3. `quantity` (Integer) and `qty` (Char) track item quantities.
4. `items` (Many2many to `product.product`) links repair materials.
5. Sale order lifecycle boolean flags (`valid_confirmed_so`, `valid_confirmed2_so`,
   `valid_delivered_so`, `valid_invoiced_so`) reflect the linked SO status.
6. `sale_order` computed field (Many2one to `sale.order`) extracts the related SO from FSM tasks.
7. Smart buttons for Sales Orders and Invoices show counts and link to filtered views.

#### Business Rules
- `sale_order` is computed from FSM task's `sale_order_id` if FSM integration is active.
- SO lifecycle flags are set by the business logic when the linked SO reaches each milestone.
- `invoice_stage_updated` boolean flag indicates the ticket stage was updated on invoicing.

#### Data Requirements
```python
{
    'balance_due': fields.Float(string='Balance Due', tracking=True),
    'sales_price': fields.Char(string='Sales Price'),
    'unit_price': fields.Float(string='Unit Price'),
    'quantity': fields.Integer(string='Quantity', default=1),
    'qty': fields.Char(string='Qty'),
    'items': fields.Many2many('product.product', string='Items'),
    'sale_order': fields.Many2one('sale.order', string='Sale Order',
                                  compute='_compute_sale_order', store=True),
    'valid_confirmed_so': fields.Boolean(string='SO Confirmed'),
    'valid_confirmed2_so': fields.Boolean(string='SO Confirmed (2)'),
    'valid_delivered_so': fields.Boolean(string='SO Delivered'),
    'valid_invoiced_so': fields.Boolean(string='SO Invoiced'),
    'invoice_stage_updated': fields.Boolean(string='Invoice Stage Updated'),
}
```

---

### FR-013 — Repair Reason Mandatory Before Plan Intervention

**Priority:** High

**User Story:** As a service manager, I want to ensure every repair ticket has a repair reason
assigned before the technician can plan an intervention, so that diagnosis data is always captured
before work begins.

#### Acceptance Criteria
1. Field `repair_reason_id` (Many2one to `jinstage.repair.reason`) is present on the ticket.
2. `action_plan_intervention` raises a `UserError` if `repair_reason_id` is not set.
3. The field is displayed on the Repair Info tab of the ticket form view.
4. The field is required before the "Plan Intervention" button becomes functional.

#### Business Rules
- `repair_reason_id` links to the `jinstage.repair.reason` master data model.
- The guard in `action_plan_intervention` is: if not `self.repair_reason_id`, raise `UserError`.
- Existing tickets without a reason set are not auto-assigned — the agent must select one.

#### Data Requirements
```python
{
    'repair_reason_id': fields.Many2one(
        'jinstage.repair.reason', string='Repair Reason', tracking=True,
        help='Reason for repair. Required before planning an intervention.'
    ),
}
```

---

### FR-014 — Plan Intervention Action

**Priority:** High

**User Story:** As a service technician, I want a "Plan Intervention" button that creates or opens
the FSM task for the repair ticket, so that I can schedule and track the repair work in the Field
Service module.

#### Acceptance Criteria
1. A `Plan Intervention` button is available on the ticket form once the item has been received
   at the factory (`receive_at_factory = True`) and a repair reason has been assigned.
2. `action_plan_intervention` guards:
   - Raises `UserError` if `receive_at_factory = False`.
   - Raises `UserError` if `repair_reason_id` is not set.
3. The method opens or creates the FSM task associated with the ticket.
4. Sets `repair_started_stage_updated = True` after successfully triggering the FSM task view.

#### Business Rules
- Guard 1: `receive_at_factory` must be True — the item must be physically at the factory.
- Guard 2: `repair_reason_id` must be set — diagnosis must be recorded before work starts.
- The method delegates FSM task creation/view to the existing `helpdesk_fsm` integration.
- Button visibility: `invisible="receive_at_factory == False or repair_started_stage_updated == True"`

#### Method Signature
```python
def action_plan_intervention(self):
    """Open FSM task for repair intervention planning.
    Guards: receive_at_factory must be True; repair_reason_id must be set.
    Sets repair_started_stage_updated = True on success.
    """
    self.ensure_one()
    if not self.receive_at_factory:
        raise UserError(_('Item must be received at factory before planning an intervention.'))
    if not self.repair_reason_id:
        raise UserError(_('Please set a Repair Reason before planning an intervention.'))
    self.write({'repair_started_stage_updated': True})
    # Return FSM task action (delegates to helpdesk_fsm)
    return self.action_view_fsm_tasks()
```

---

### FR-015 — Repair Diagnosis Master Data

**Priority:** Medium

**User Story:** As a service manager, I want configurable master data tables for repair diagnosis
(symptom areas, symptom codes, conditions, diagnosis areas, diagnosis codes, repair reasons,
sub-reasons, resolutions), so that technicians select from standardised diagnosis entries instead
of typing free text.

#### Acceptance Criteria
1. Eight master data models are created under the `jinstage_helpdesk_repair` module.
2. Each model has at minimum `name` (Char, required) and `active` (Boolean, default=True).
3. Menu items under Helpdesk > Configuration > Repair Diagnosis provide CRUD access.
4. Models follow the naming convention `jinstage.repair.<entity>`.

#### Business Rules
- Master data models: `jinstage.repair.symptom.area`, `jinstage.repair.symptom.code`,
  `jinstage.repair.condition`, `jinstage.repair.diagnosis.area`,
  `jinstage.repair.diagnosis.code`, `jinstage.repair.reason`, `jinstage.repair.reason.customer`,
  `jinstage.repair.sub.reason`, `jinstage.repair.resolution`.
- Helpdesk manager group required for configuration menu access.

#### Data Requirements
```python
class JinstageRepairSymptomArea(models.Model):
    _name = 'jinstage.repair.symptom.area'
    _description = 'Repair Symptom Area'
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    code = fields.Char(string='Code')
    description = fields.Text()
```

---

### FR-016 — Five PDF Reports

**Priority:** High

**User Story:** As a service agent, I want to print standardised PDF reports for repair intake,
status updates, completion notices, and scrappage write-offs, so that customers and internal staff
receive professional documentation at each stage.

#### Acceptance Criteria
1. Five `ir.actions.report` records are defined on `helpdesk.ticket`:
   - **Repair Final Notice** (EUR A4) — completion notice to customer
   - **Repair Receipt** (US Letter) — intake receipt
   - **Repair Status** (Default) — internal operational status
   - **Helpdesk Ticket Report** (Default) — full ticket details
   - **Repair Final Notice — Scrappage** (US Letter) — write-off jobs
2. Each report uses a dedicated QWeb template with company header, ticket details, and appropriate
   footer.
3. Paper formats are configured (`report.paperformat`) with the correct sizes.
4. Reports are accessible from the Print menu on the ticket form.

#### Business Rules
- All five reports print on `helpdesk.ticket` records.
- Repair Final Notice and Scrappage use US Letter and EUR A4 respectively.
- Reports must not expose internal-only fields to customer-facing outputs.

---

### FR-017 — Reverse Transfer Approval Rule

**Priority:** High

**User Story:** As a warehouse manager, I want an approval rule enforcing that only authorised users
can validate a reverse (return) stock transfer associated with a repair, so that accidental or
unauthorised reversals are prevented.

#### Acceptance Criteria
1. An `approval.rule` record (or equivalent Odoo 17 approval mechanism) named
   "Helpdesk Ticket / Reverse Transfer" is configured on `stock.picking`.
2. The rule requires `base.group_user` approval before a reverse transfer can be validated.
3. The rule is active and applied to all reverse transfer pickings linked to helpdesk tickets.

#### Business Rules
- Applies specifically to reverse transfer (return) pickings.
- All internal users must receive approval before proceeding with reversals.

---

### FR-016 — Kanban Status Visibility

**Priority:** Low

**User Story:** As a service team lead, I want repair-specific status badges on the kanban cards so
that I can assess repair progress at a glance without opening individual tickets.

#### Acceptance Criteria
1. The helpdesk ticket kanban view is extended to display a repair type badge derived from
   the four type booleans (`rug_repair`, `rug_confirmed`, `normal_repair_with_serial_no`,
   `normal_repair_without_serial_no`). `rug_approval_status` chip is only shown when
   `rug_confirmed = True`.
2. `quick_repair_status` and `material_availability` status fields appear as colour-coded chips.
3. The kanban card respects the existing helpdesk kanban view structure via xpath inheritance.

#### Business Rules
- Badge colours: Under Warranty RUG = warning/orange, Under Warranty External = info/blue,
  Not Under Warranty Serial = success/green, Not Under Warranty No Serial = secondary/grey.
- `rug_approval_status` badge only visible on kanban when `rug_confirmed = True` (RUG type only).
- Status fields use selection list values for colour mapping.

#### Data Requirements
```python
{
    'quick_repair_status': fields.Selection([...], string='Quick Repair Status',
                                             tracking=True),
    'material_availability': fields.Selection([...], string='Material Availability',
                                               tracking=True),
}
```

---

### FR-017 — List View Repair Columns

**Priority:** Low

**User Story:** As a service manager, I want the helpdesk ticket list view to include repair-specific
columns, so that I can manage repair tickets from the list without needing to open each record.

#### Acceptance Criteria
1. A custom list view (priority 900) extends the base helpdesk ticket tree view with columns:
   - Repair type indicator, serial number, repair location, stage, RUG approval status,
     centre/factory movement flags, balance due.
2. The view is sortable by repair type and stage date.
3. List view is accessible from the Helpdesk main menu.

---

### FR-018 — FSM Task Integration

**Priority:** High

**User Story:** As a field service dispatcher, I want helpdesk repair tickets to integrate with
FSM tasks so that field technicians' task completion automatically updates the repair ticket status.

#### Acceptance Criteria
1. `fsm_task_done` computed boolean on `helpdesk.ticket` is True when all linked FSM
   (`project.task`) tasks are in done state.
2. `sale_order` computed field extracts `sale_order_id` from the linked FSM task.
3. Smart button "FSM Tasks" on the ticket header shows count and links to filtered task list.
4. `handed_over` boolean (readonly) is set when the FSM task is completed and the item handed
   to the customer.

#### Business Rules
- `fsm_task_done` depends on `use_helpdesk_fsm` feature flag being active.
- `sale_order` is only populated when exactly one FSM task exists with a linked sale order.

#### Data Requirements
```python
{
    'fsm_task_done': fields.Boolean(
        string='FSM Task Done',
        compute='_compute_fsm_task_done',
        store=False,
    ),
    'handed_over': fields.Boolean(string='Handed Over', readonly=True,
                                   tracking=True),
}
```

---

### FR-019 — Stage Change Timestamp

**Priority:** Medium

**User Story:** As an operations analyst, I want each ticket to record when its stage last changed,
so that I can calculate repair cycle times and SLA compliance.

#### Acceptance Criteria
1. `stage_date` Datetime field records the timestamp of the most recent stage change.
2. The field is updated automatically via ORM `write` override when `stage_id` changes.
3. `stage_date` is readonly on the form view and displayed in the Extra Info tab.

#### Business Rules
- `stage_date` is set to `fields.Datetime.now()` at the moment `stage_id` is written.
- Initial creation sets `stage_date` to the ticket creation timestamp.

---

### FR-020 — Reporting Menus

**Priority:** Low

**User Story:** As a service manager, I want dedicated reporting menu items under Helpdesk Reporting
to access repair-specific data reports, so that I can generate operational reports without custom
searches.

#### Acceptance Criteria
1. Under Helpdesk > Reporting, two active menu items:
   - **Repair Job Details** — list/pivot view of repair tickets with key metrics.
   - **Repair Sales Order List** — list view linking repair tickets to their sale orders.
2. Two inactive menu items (available for activation):
   - **Repair Job Details RUG Only** — filtered view for RUG repairs.
   - **Customer Letter Report** — customer communication report.
3. All menus link to `ir.actions.act_window` actions on `helpdesk.ticket`.

---

## User Stories by Repair Type Workflow

### Workflow A — Under Warranty — RUG Repair

**Ticket type flags:** `is_rug = True`, `is_rug_confirmed = True`

**As a service agent, I want to:**
1. Create a ticket, select "Repair - Under Warranty - RUG" type → `rug_repair = True`,
   `rug_confirmed = True`.
2. Assign four location fields and customer details.
3. Create the return transfer (reverse picking to receive item into repair location).
4. Send item to factory (`send_to_factory`), mark received at factory (`receive_at_factory`).
5. Set `repair_reason_id` and click "Plan Intervention" → FSM task created/opened.
6. Add products/parts to FSM task → quotation (SO) is generated automatically.
7. Send RUG approval request → `rug_request_sent = True`, `rug_approval_status = 'pending'`.
   _(RUG approval requires the quotation to exist — `sale_order` must be set.)_
8. Manager approves → `rug_approved = True`.
9. Customer confirms the SO → `valid_confirmed_so = True`.
10. 50% advance invoice created → `advance_invoice_created = True`.
11. Repair work completed, FSM task done → `fsm_task_done = True`.
12. Remaining balance invoice generated → `valid_invoiced_so = True`, `invoice_stage_updated = True`.
13. Send item to sales centre (`send_to_centre`), mark received (`receive_at_centre`).
14. Item handed over to customer → `handed_over = True`.

### Workflow B — Under Warranty — External not RUG

**Ticket type flags:** `is_rug = True`, `is_rug_confirmed = False`

**As a service agent, I want to:**
1. Create a ticket, select "Repair - Under Warranty - External not RUG" type →
   `rug_repair = True`, `rug_confirmed = False`.
2. Assign location fields and customer details.
3. Create the return transfer.
4. Send item directly to factory (`send_to_factory`), no RUG approval step required.
5. Mark received at factory (`receive_at_factory`).
6. Set `repair_reason_id` and plan intervention.
7. Repair completed by external service provider, estimate provided, customer confirms SO.
8. Invoice and dispatch to sales centre, hand over.
   _(No "Send RUG Request" or "Approve RUG" buttons appear for this type.)_

### Workflow C — Not Under Warranty With Serial Number

**Ticket type flags:** `is_with_serial_no = True`

**As a service agent, I want to:**
1. Create a ticket with "Repair - Not Under Warranty (With Serial No)" type →
   `normal_repair_with_serial_no = True`.
2. Create or link a serial number (stock.lot) → `repair_serial_created = True`.
3. Assign locations and create return transfer.
4. Send item to factory, receive at factory.
5. Set `repair_reason_id`, plan intervention, complete FSM tasks → `fsm_task_done = True`.
6. Customer confirms SO, 50% advance invoice, repair, balance invoice.
7. Send to sales centre, hand over.

### Workflow D — Not Under Warranty Without Serial Number

**Ticket type flags:** `is_without_serial_no = True`

**As a service agent, I want to:**
1. Create a ticket with "Repair - Not Under Warranty (Without Serial No)" type →
   `normal_repair_without_serial_no = True`.
2. Optionally create an internal reference serial number for tracking.
3. Assign repair location (minimum), create return transfer.
4. Send item to factory, receive at factory.
5. Set `repair_reason_id`, plan intervention, proceed to repair, estimate, invoice.
6. Send to sales centre, hand over item.

---

## User Interface Requirements

### Form Views

**Repair Ticket Form (helpdesk.ticket):**
- **Header:** Status bar (`stage_id`), 10 conditional action buttons:
  1. Create Return Transfer
  2. Send to Factory
  3. Receive at Factory
  4. Plan Intervention
  5. Send RUG Request (RUG repairs only)
  6. Send to Sales Centre
  7. Receive at Sales Centre
  8. Cancel
  9. Reopen
- **Smart Buttons:** FSM Tasks (count), Sale Orders (count), Invoices (count), Repair Trans (count)
- **Main Tab:** Customer info, repair type, serial number, warranty card, document fields,
  driver/vehicle info
- **Description Tab:** Standard helpdesk description field
- **Extra Info Tab:** Location fields, workflow status flags, financial fields, stage date,
  user tracking
- **Cancel/Reopen Log Tab:** Audit trail fields (cancelled_by, dates, stages, reasons)

**Stage Form (helpdesk.stage):** `company_id` field added

**Ticket Type Tree (helpdesk.ticket.type):** `is_rug`, `is_rug_confirmed`, `is_with_serial_no`,
`is_without_serial_no` columns added — displays the flag matrix for all four repair types.

### List Views

- **Repair Ticket List (priority 900):** Columns include name, partner_id, ticket_type_id,
  repair_serial_no, repair_location, stage_id, rug_approval_status, balance_due,
  send_to_centre, receive_at_centre, send_to_factory, receive_at_factory.

### Reports

- **Repair Receipt:** Customer-facing intake document, US Letter format.
- **Repair Final Notice:** Customer-facing completion document, EUR A4.
- **Repair Final Notice — Scrappage:** Customer-facing scrappage write-off, US Letter.
- **Repair Status:** Internal operational status, default format.
- **Helpdesk Ticket Report:** Full ticket printout, default format.

---

## Integration Requirements

### Odoo Stock Module (stock)

- **Trigger Points:** `picking_id` field creation, `Create Repair Route` button action.
- **Data Exchange:** `stock.location` for all four location fields, `stock.lot` for serial
  tracking, `stock.picking` bidirectional link.
- **Business Logic:** Repair route generates one or more `stock.picking` records;
  `stock.picking.helpdesk_ticket_id` references the originating ticket.
- **Location Control:** `stock.location.users_stock_location` Many2many for access control.

### FSM / Helpdesk FSM (industry_fsm, helpdesk_fsm)

- **Trigger Points:** FSM task completion triggers `fsm_task_done` recompute.
- **Data Exchange:** `project.task` linked to `helpdesk.ticket`, `sale_order_id` extracted
  from FSM task for `sale_order` computed field.
- **Business Logic:** `fsm_task_done` True when all FSM tasks in done/cancelled state.
  `handed_over` set in conjunction with FSM task completion.

### Sale / Helpdesk Sale (sale_management, helpdesk_sale)

- **Trigger Points:** SO lifecycle events update boolean flags on the ticket.
- **Data Exchange:** `sale.order` linked via computed `sale_order` field; invoice smart
  button count derived from SO invoices.
- **Business Logic:** `valid_confirmed_so`, `valid_delivered_so`, `valid_invoiced_so` reflect
  SO state progression.

### Accounting (account)

- **Trigger Points:** Invoice creation and posting from the repair ticket.
- **Data Exchange:** Invoice count for smart button, `balance_due` synchronisation.
- **Business Logic:** `invoice_stage_updated` flag set when repair stage advances post-invoice.
  Repair Accounts master data links GL accounts to repair types.

### Product (product)

- **Trigger Points:** `items` Many2many field selection.
- **Data Exchange:** `product.product` for repair materials list.
- **Business Logic:** Materials list provides parts used in repair for costing and invoicing.

### Helpdesk (helpdesk)

- **Primary Extension Target:** `helpdesk.ticket`, `helpdesk.stage`, `helpdesk.ticket.type`.
- **View Inheritance:** All views extend existing helpdesk views via xpath.
- **Group Reuse:** `helpdesk.group_helpdesk_manager` and `helpdesk.group_helpdesk_user` used
  for menu and record access control.

---

## Security and Access Control

### User Groups and Permissions

#### Helpdesk User (helpdesk.group_helpdesk_user)
- **Read Access:** All repair ticket fields
- **Write Access:** Standard repair workflow fields; cannot approve RUG
- **Create Access:** Create new repair tickets
- **Delete Access:** Draft tickets only

#### Helpdesk Manager (helpdesk.group_helpdesk_manager)
- **Full Access:** All CRUD operations on all repair models
- **Admin Functions:** Configuration menus (Repair Diagnosis master data, Repair Accounts)
- **RUG Approval:** Approve or reject RUG repair requests
- **Reports:** Access to all five PDF reports and all reporting menus

#### Base User (base.group_user)
- **Reverse Transfer Approval:** Can request but requires approval before validating
  reverse stock transfers linked to repair tickets

### Record-Level Security

- **Multi-Company:** Helpdesk stages filtered by `company_id` via automation rule.
- **Location-Based:** `user_location_validation` restricts certain operations to permitted users.
- **Team-Based:** Standard helpdesk team visibility rules apply to repair tickets.

### Data Privacy

- **PII Handling:** Customer name, contact details stored via standard `res.partner` on ticket;
  no additional PII storage beyond `cancelled_by`, `reopened_by` user references.
- **Audit Trail:** Cancel/Reopen log fields are write-once (set on action, not editable directly).
- **Warranty Card:** Binary image stored as attachment; accessible only to helpdesk team members.

---

## Performance Requirements

### Response Time
- **Ticket Form Load:** Within 2 seconds including all computed fields.
- **Kanban View:** 50-card kanban renders within 2 seconds.
- **List View:** 200-row list view with repair columns returns within 1 second.
- **Report Generation:** PDF reports complete within 30 seconds for single records.
- **Bulk Stage Updates:** Processing 100+ ticket stage updates within 2 minutes.

### Scalability
- **Concurrent Users:** Support 30+ simultaneous helpdesk agents.
- **Data Volume:** Handle 50,000+ repair tickets with performant list and kanban views.
- **Stored Computed Fields:** `rug_repair`, `normal_repair_with_serial_no`,
  `normal_repair_without_serial_no`, `sale_order` are stored to support efficient list filtering.

### Availability
- **Uptime:** 99.5% availability during business hours.
- **Backup:** Daily automated backups.

---

## Odoo 17 Specific Constraints

### Technical Constraints
- **Odoo Version:** Must be compatible with Odoo 17.0 Enterprise.
- **Database:** PostgreSQL 14+ required.
- **Python Version:** Python 3.10+ (Odoo 17 requirement).
- **No Deprecated APIs:** Must not use `@api.multi`, `@api.one`, `attrs=` XML attribute
  (use `invisible=`, `required=`, `readonly=` domain expressions instead), or `_columns`.
- **Odoo 17 Domain Syntax:** Use Python-like domain expressions in views
  (`invisible="rug_repair == False"` not `attrs="{'invisible': [...]}"`)
- **No Studio Prefix:** All fields use clean names (no `x_studio_` prefix).
- **QWeb Reports:** Use `ir.actions.report` with `report_type='qweb-pdf'`.
- **ir.model.access.csv:** Must cover all new models and all inherited model extensions.

### Module Dependencies
```python
# __manifest__.py
'depends': [
    'helpdesk',
    'helpdesk_fsm',
    'helpdesk_sale',
    'industry_fsm',
    'stock',
    'sale_management',
    'account',
    'product',
],
```

### Upgrade Compatibility
- All new columns added via `_inherit` approach — no direct schema modification.
- Data migration not required for v1.0.0 (fresh installation).
- Module must be installable on a clean Odoo 17 Enterprise database with the above dependencies.

---

## Non-Functional Requirements

### Code Quality
- **Coding Standards:** PEP 8 for Python; Odoo XML naming conventions for views.
- **Documentation:** All public methods have docstrings; complex business logic has inline comments.
- **Test Coverage:** Unit tests cover all business logic methods; integration tests cover all
  all four repair type workflows (Under Warranty - RUG, Under Warranty - External not RUG,
  Not Under Warranty With Serial, Not Under Warranty Without Serial).
- **No Magic Numbers:** All selection values and constants defined as class-level attributes
  or separate data files.

### Maintainability
- **No Studio Dependency:** All customisations must work without Studio being installed.
- **Modular Design:** Business logic in model methods; presentation in XML only.
- **File Organisation:** Each model in its own Python file; views split by model.

### Compliance
- **Odoo Guidelines:** Follows official Odoo 17 development guidelines.
- **LGPL-3:** Module licence is LGPL-3 (Odoo community standard).

---

## Constraints and Assumptions

### Technical Constraints
- The module is an extension (not a replacement) of `helpdesk`.
- Studio customisations on the target database must be removed before installation.
- `x_studio_` field names from Studio must be mapped to clean field names during data migration.
- The `approval` module (for reverse transfer approval rules) must be installed.

### Business Constraints
- Go-live target: within 60 days of specification approval.
- Development team: 1-2 Odoo developers.
- Training required for service managers (RUG approval) and service agents (new UI).

### Assumptions
- Helpdesk FSM (`helpdesk_fsm`) and Helpdesk Sale (`helpdesk_sale`) are installed and active.
- The `industry_fsm` module is installed (Field Service Management).
- At least one `helpdesk.team` exists with active repair stages.
- `ir.sequence` code `repair.seq` does not pre-exist in the database.
- Existing Studio data will be migrated or discarded before module installation.

---

## Success Criteria and Acceptance

### Functional Success Criteria
1. All 20 functional requirements implemented and passing acceptance criteria.
2. Three repair type workflows (A, B, C) complete end-to-end without errors.
3. All five PDF reports generate without errors for sample data.
4. RUG approval workflow enforces stage gating correctly.
5. Cancel/Reopen audit trail fields are populated correctly on all cancel/reopen actions.

### Technical Success Criteria
1. Module installs cleanly on a fresh Odoo 17 Enterprise database.
2. All unit and integration tests pass.
3. No `x_studio_` field references remain in the codebase.
4. No deprecated Odoo API usage.
5. No JavaScript errors in browser console during normal operation.

### Business Success Criteria
1. 100% of repair tickets assigned a unique repair sequence number.
2. RUG repairs cannot proceed to factory without manager approval.
3. Zero untracked cancellations (all cancellations logged with user and timestamp).
4. Location-based access control operational for all configured locations.

---

## Risk Assessment

### High-Risk Items
1. **Studio Migration:** Mapping `x_studio_` field names to clean names while preserving existing
   data.
   - **Mitigation:** Pre-migration SQL mapping script; staged rollout.
   - **Contingency:** Retain `x_studio_` aliases temporarily via related fields.

2. **FSM/Sale Integration Complexity:** `sale_order` computed field depends on FSM task data
   structure which varies by configuration.
   - **Mitigation:** Defensive coding with try/except; field stores=True for resilience.
   - **Contingency:** Manual `sale_order` field if computed approach fails.

### Medium-Risk Items
1. **Approval Module Compatibility:** Odoo 17 approval mechanism may differ from Studio-based
   approval rules.
   - **Mitigation:** Test approval rule creation in Odoo 17 sandbox early in Phase 7.
   - **Contingency:** Implement approval as a manual workflow step with group-restricted button.

2. **Report Paper Formats:** Custom paper format records may conflict with existing formats.
   - **Mitigation:** Use unique `id` and `name` values; check for existing formats before creation.

---

## Glossary

**Business Terms:**
- **RUG Repair:** A special repair category (high-value or warranty-class) requiring management
  approval before factory work commences.
- **Repair Route:** A set of stock picking records that track the physical movement of the item
  through the repair pipeline.
- **Service Centre:** An intermediate facility where items are inspected before/after factory repair.
- **Factory:** The main repair facility where the actual technical repair work is performed.
- **Handover:** The final step where a repaired item is returned to the customer.
- **Repair Sequence:** The unique reference number (`REP/YYYY/NNNNN`) assigned to each repair ticket.

**Technical Terms:**
- **helpdesk.ticket:** Odoo's core support ticket model, extended by this module.
- **stock.lot:** Odoo's serial number / lot model used for serial-tracked items.
- **stock.picking:** Odoo's stock transfer model used for repair route movements.
- **ir.sequence:** Odoo's configurable sequence number generator.
- **ir.rule:** Odoo's record-level security rule model.
- **QWeb:** Odoo's XML-based templating engine used for PDF report generation.
- **FSM:** Field Service Management — Odoo's industry_fsm module for on-site technician tasks.
- **xpath:** XML path expression used to inject fields into inherited Odoo views.

---

**Document Status:** Draft
**Last Updated:** 2026-04-08
**Next Review Date:** 2026-04-15
**Approved By:** Pending
