# Odoo Module Design Document - jinstage_helpdesk_repair

## Module Overview

**Module Name:** jinstage_helpdesk_repair
**Technology Stack:** Python 3.10+ + Odoo 17.0 Enterprise
**Database:** PostgreSQL 14+
**Architecture Pattern:** MVC (Model-View-Controller) with Odoo _inherit extension pattern

---

## Steering Documents Alignment

### Technical Stack
- **Python Version:** Python 3.10+ (Odoo 17 requirement)
- **Code Style:** PEP 8 + Odoo coding guidelines; no deprecated APIs
- **Database Design:** PostgreSQL best practices; proper indexes on high-frequency query fields

### Module Standards
- **Module Structure:** Standard Odoo module directory layout
- **File Naming:** Descriptive names per model (no module-prefix filenames)
- **Version Control:** Semantic versioning starting at 17.0.1.0.0

### Business Rules
- **Workflow:** Repair lifecycle enforced via method-level guards and computed fields
- **Access Control:** `helpdesk.group_helpdesk_manager` for admin functions
- **Data Processing:** All PII via `res.partner` linkage; cancel/reopen audit trail immutable

---

## Code Reuse Analysis

### Existing Component Utilisation
- **helpdesk.ticket:** Primary base model extended via `_inherit`
- **helpdesk.stage:** Extended for company scoping
- **helpdesk.ticket.type:** Extended for repair type flags
- **stock.picking / stock.lot / stock.location:** Extended for bidirectional linking and location control
- **mail.thread / mail.activity.mixin:** Already on `helpdesk.ticket`; tracking=True used throughout
- **ir.sequence:** Reused for repair sequence (`repair.seq`)
- **ir.actions.report (qweb-pdf):** Five report actions on `helpdesk.ticket`

### Integration Points
- **helpdesk_fsm:** FSM task link for `fsm_task_done` and `sale_order` computed fields
- **helpdesk_sale:** SO smart button count; SO lifecycle flag synchronisation
- **industry_fsm:** `project.task` with `is_fsm=True` and `sale_order_id`
- **account:** Invoice count smart button; `balance_due` tracking
- **stock:** Location fields, serial lots, picking route

---

## System Architecture

### Module Structure Design

```
jinstage_helpdesk_repair/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── helpdesk_ticket.py          # Main ticket extension (~60 fields + methods)
│   ├── helpdesk_stage.py           # Stage company_id extension
│   ├── helpdesk_ticket_type.py     # Type flags extension
│   ├── stock_picking.py            # Bidirectional picking link
│   ├── stock_location.py           # Permitted users M2M
│   ├── repair_symptom_area.py      # Diagnosis master data
│   ├── repair_symptom_code.py
│   ├── repair_condition.py
│   ├── repair_diagnosis_area.py
│   ├── repair_diagnosis_code.py
│   ├── repair_reason.py
│   ├── repair_reason_customer.py
│   ├── repair_sub_reason.py
│   └── repair_resolution.py
├── views/
│   ├── helpdesk_ticket_views.xml   # Form, kanban, list view extensions
│   ├── helpdesk_stage_views.xml    # Stage form/tree extensions
│   ├── helpdesk_ticket_type_views.xml
│   ├── diagnosis_views.xml         # Master data views
│   ├── actions.xml                 # ir.actions.act_window records
│   └── menus.xml                   # Menu items
├── security/
│   ├── ir.model.access.csv
│   └── record_rules.xml
├── data/
│   ├── ir_sequence_data.xml        # repair.seq definition
│   └── automation_rules.xml        # 3 automation rules
├── report/
│   ├── report_actions.xml          # 5 ir.actions.report records
│   ├── report_repair_receipt.xml
│   ├── report_repair_status.xml
│   ├── report_repair_final_notice.xml
│   ├── report_repair_final_notice_scrappage.xml
│   ├── report_helpdesk_ticket.xml
│   └── paper_formats.xml
├── tests/
│   ├── __init__.py
│   ├── test_repair_workflow.py
│   └── test_repair_integration.py
└── static/
    └── description/
        └── icon.png
```

---

## Data Model Design

### 1. helpdesk.ticket Extension

```python
class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    # --- Identification & Tracking ---
    repair_serial_no = fields.Many2one(
        'stock.lot', string='Serial Number', tracking=True,
        domain="[('product_id', '=', product_id)]"
    )
    serial_number = fields.Many2one(
        'stock.lot', string='Serial Number (Legacy)'
    )
    picking_id = fields.Many2one(
        'stock.picking', string='Receipt Picking', tracking=True
    )
    driver_name = fields.Char(string='Driver Name')
    vehicle_details = fields.Char(string='Vehicle Details')

    # --- Sale Order (Computed from FSM) ---
    sale_order = fields.Many2one(
        'sale.order', string='Sale Order',
        compute='_compute_sale_order', store=True
    )

    # --- Location Management ---
    repair_location = fields.Many2one(
        'stock.location', string='Repair Location',
        domain="[('usage', 'in', ['internal', 'transit'])]"
    )
    return_receipt_location = fields.Many2one(
        'stock.location', string='Return Receipt Location'
    )
    source_location = fields.Many2one(
        'stock.location', string='Source Location'
    )
    job_location = fields.Many2one(
        'stock.location', string='Job Location'
    )

    # --- Repair Type Related Booleans (mirror ticket_type_id flags) ---
    # rug_repair: True for BOTH "Under Warranty - RUG" AND "Under Warranty - External not RUG"
    rug_repair = fields.Boolean(
        related='ticket_type_id.is_rug', store=True,
        string='RUG Repair'
    )
    # rug_confirmed: True ONLY for "Under Warranty - RUG"; False for External not RUG
    # This is the key distinguisher — gates the full internal approval workflow
    rug_confirmed = fields.Boolean(
        related='ticket_type_id.is_rug_confirmed', store=True,
        string='RUG Confirmed'
    )
    normal_repair_with_serial_no = fields.Boolean(
        related='ticket_type_id.is_with_serial_no', store=True,
        string='Normal Repair (With Serial)'
    )
    normal_repair_without_serial_no = fields.Boolean(
        related='ticket_type_id.is_without_serial_no', store=True,
        string='Normal Repair (No Serial)'
    )

    # --- Workflow Status Selections ---
    quick_repair_status = fields.Selection([
        ('not_started', 'Not Started'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('on_hold', 'On Hold'),
    ], string='Quick Repair Status', tracking=True)

    cancel_status = fields.Selection([
        ('customer_request', 'Customer Request'),
        ('beyond_repair', 'Beyond Repair'),
        ('no_spare_parts', 'No Spare Parts Available'),
        ('other', 'Other'),
    ], string='Cancellation Reason', tracking=True)

    reopen_status = fields.Selection([
        ('customer_request', 'Customer Request'),
        ('error_correction', 'Error Correction'),
        ('re_estimate', 'Re-Estimation Required'),
        ('other', 'Other'),
    ], string='Reopen Reason', tracking=True)

    re_estimate_status = fields.Selection([
        ('pending', 'Pending'),
        ('sent', 'Sent to Customer'),
        ('approved', 'Customer Approved'),
        ('rejected', 'Customer Rejected'),
    ], string='Re-Estimate Status', tracking=True)

    rug_approval_status = fields.Selection([
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='RUG Approval Status', tracking=True)

    material_availability = fields.Selection([
        ('available', 'Available'),
        ('partial', 'Partially Available'),
        ('unavailable', 'Unavailable'),
        ('ordered', 'Ordered'),
    ], string='Material Availability', tracking=True)

    stage_date = fields.Datetime(string='Stage Changed Date', tracking=True)
    cancelled_date = fields.Datetime(string='Cancelled Date')
    reopened_date = fields.Datetime(string='Reopened Date')
    cancelled_stage_id = fields.Many2one(
        'helpdesk.stage', string='Stage at Cancellation'
    )

    # --- Boolean Workflow Flags ---
    send_to_centre = fields.Boolean(
        string='Send to Centre', default=False, tracking=True
    )
    receive_at_centre = fields.Boolean(
        string='Received at Centre', default=False, tracking=True
    )
    send_to_factory = fields.Boolean(
        string='Send to Factory', default=False, tracking=True
    )
    receive_at_factory = fields.Boolean(
        string='Received at Factory', default=False, tracking=True
    )
    handed_over = fields.Boolean(
        string='Handed Over', readonly=True, default=False, tracking=True
    )
    fsm_task_done = fields.Boolean(
        string='FSM Task Done',
        compute='_compute_fsm_task_done',
        store=False
    )
    cancelled = fields.Boolean(
        string='Cancelled', default=False, tracking=True
    )
    cancelled_2 = fields.Boolean(
        string='Cancelled (Stage 2)', default=False
    )
    repair_serial_created = fields.Boolean(
        string='Serial Created', default=False
    )
    sn_updated = fields.Boolean(
        string='Serial Number Updated', default=False
    )
    rug_confirmed = fields.Boolean(
        string='RUG Confirmed', default=False, tracking=True
    )
    rug_approved = fields.Boolean(
        string='RUG Approved', default=False, tracking=True
    )
    rug_request_sent = fields.Boolean(
        string='RUG Request Sent', default=False, tracking=True
    )
    valid_confirmed_so = fields.Boolean(
        string='SO Confirmed', default=False
    )
    valid_confirmed2_so = fields.Boolean(
        string='SO Confirmed (2)', default=False
    )
    valid_delivered_so = fields.Boolean(
        string='SO Delivered', default=False
    )
    valid_invoiced_so = fields.Boolean(
        string='SO Invoiced', default=False
    )
    repair_started_stage_updated = fields.Boolean(
        string='Repair Started Stage Updated', default=False
    )
    estimation_approved_stage_updated = fields.Boolean(
        string='Estimation Approved Stage Updated', default=False
    )
    invoice_stage_updated = fields.Boolean(
        string='Invoice Stage Updated', default=False
    )
    advance_invoice_created = fields.Boolean(
        string='Advance Invoice Created', default=False, tracking=True
    )
    user_location_validation = fields.Boolean(
        string='Location Access Valid',
        compute='_compute_user_location_validation',
        store=False
    )

    # --- Repair Reason (mandatory before Plan Intervention) ---
    repair_reason_id = fields.Many2one(
        'jinstage.repair.reason', string='Repair Reason', tracking=True,
        help='Reason for repair. Required before planning an intervention (FR-013).'
    )

    # --- Audit & User Tracking ---
    cancelled_by = fields.Many2one('res.users', string='Cancelled By')
    reopened_by = fields.Many2one('res.users', string='Reopened By')
    s_received_by = fields.Many2one(
        'res.users', string='Received by (Centre)'
    )
    f_received_by = fields.Many2one(
        'res.users', string='Received by (Factory)'
    )
    s_shipped_by = fields.Many2one(
        'res.users', string='Shipped by (Centre)'
    )
    f_shipped_by = fields.Many2one(
        'res.users', string='Shipped by (Factory)'
    )
    created_by_1 = fields.Many2one('res.users', string='Created By (1)')
    created_by_2 = fields.Many2one('res.users', string='Created By (2)')
    created_by_3 = fields.Many2one('res.users', string='Created By (3)')
    # ... created_by_4 through created_by_10 follow same pattern

    # --- Financial & Product ---
    balance_due = fields.Float(string='Balance Due', tracking=True)
    sales_price = fields.Char(string='Sales Price')
    unit_price = fields.Float(string='Unit Price')
    quantity = fields.Integer(string='Quantity', default=1)
    qty = fields.Char(string='Qty')
    items = fields.Many2many(
        'product.product', string='Items',
        relation='helpdesk_ticket_product_rel',
        column1='ticket_id', column2='product_id'
    )

    # --- Documents ---
    warranty_card = fields.Binary(
        string='Warranty Card', attachment=True
    )
    related_information = fields.Binary(
        string='Related Information', attachment=True
    )

    # --- Picking Smart Button ---
    picking_ids = fields.Many2many(
        'stock.picking',
        compute='_compute_picking_ids',
        string='Pickings'
    )
    picking_count = fields.Integer(
        compute='_compute_picking_ids', string='Picking Count'
    )
```

#### Computed Field Implementations

```python
    # NOTE: rug_repair, rug_confirmed, normal_repair_with_serial_no,
    # normal_repair_without_serial_no are related fields — no _compute_repair_type method needed.
    # Odoo's related field mechanism handles propagation and store=True recomputation
    # when the ticket_type_id changes.

    @api.depends('task_ids', 'task_ids.stage_id',
                 'task_ids.stage_id.is_closed')
    def _compute_fsm_task_done(self):
        for ticket in self:
            tasks = ticket.task_ids
            if not tasks:
                ticket.fsm_task_done = False
            else:
                ticket.fsm_task_done = all(
                    t.stage_id.is_closed for t in tasks
                )

    @api.depends('task_ids', 'task_ids.sale_order_id')
    def _compute_sale_order(self):
        for ticket in self:
            sale_orders = ticket.task_ids.mapped('sale_order_id')
            ticket.sale_order = sale_orders[:1] if sale_orders else False

    def _compute_user_location_validation(self):
        for ticket in self:
            loc = ticket.repair_location
            if not loc or not loc.users_stock_location:
                ticket.user_location_validation = True
            else:
                ticket.user_location_validation = (
                    self.env.user in loc.users_stock_location
                )

    @api.depends('helpdesk_ticket_id')
    def _compute_picking_ids(self):
        # Called on helpdesk.ticket via inverse relationship
        for ticket in self:
            pickings = self.env['stock.picking'].search([
                ('helpdesk_ticket_id', '=', ticket.id)
            ])
            ticket.picking_ids = pickings
            ticket.picking_count = len(pickings)
```

#### ORM Override for stage_date

```python
    def write(self, vals):
        if 'stage_id' in vals:
            vals['stage_date'] = fields.Datetime.now()
        return super().write(vals)
```

#### Action Button Method Signatures

```python
    def action_create_repair_route(self):
        """Create stock.picking records for the repair route."""
        self.ensure_one()
        # Validate required location fields are set
        # Create inbound picking (customer → repair_location)
        # Create outbound picking (repair_location → customer)
        # Set picking_id to inbound picking
        ...

    def action_send_to_factory(self):
        """Mark item as dispatched to factory.
        CORRECT ORDER: factory FIRST (directly after return transfer), then
        sales centre AFTER repair completion.
        Guard: picking_count > 0 (return transfer must exist).
        No centre prerequisite — item goes directly from intake to factory.
        No RUG approval gate here — approval now gates SO confirmation, not factory dispatch.
        """
        self.ensure_one()
        if not self.picking_count:
            raise UserError(_('Create the return transfer before sending to factory.'))
        self.write({
            'send_to_factory': True,
            'f_shipped_by': self.env.uid,
            'stage_date': fields.Datetime.now(),
        })

    def action_receive_at_factory(self):
        """Mark item as received at factory."""
        self.ensure_one()
        if not self.send_to_factory:
            raise UserError(_('Item must be sent to factory first.'))
        self.write({
            'receive_at_factory': True,
            'f_received_by': self.env.uid,
            'stage_date': fields.Datetime.now(),
        })

    def action_send_to_centre(self):
        """Mark item as dispatched to sales centre AFTER repair completion.
        Guard: receive_at_factory must be True — repair at factory must be
        complete before the item is dispatched to the sales centre for handover.
        """
        self.ensure_one()
        if not self.receive_at_factory:
            raise UserError(_('Item must be received at factory (repair complete) before sending to sales centre.'))
        self.write({
            'send_to_centre': True,
            's_shipped_by': self.env.uid,
            'stage_date': fields.Datetime.now(),
        })

    def action_receive_at_centre(self):
        """Mark item as received at sales centre for customer handover."""
        self.ensure_one()
        if not self.send_to_centre:
            raise UserError(_('Item must be sent to sales centre first.'))
        self.write({
            'receive_at_centre': True,
            's_received_by': self.env.uid,
            'stage_date': fields.Datetime.now(),
        })

    def action_send_rug_request(self):
        """Send RUG approval request to managers.
        TIMING: Called AFTER the quotation (SO) is created and BEFORE customer SO confirmation.
        Only available when rug_repair=True AND rug_confirmed=True
        (i.e. type is 'Under Warranty - RUG'). External not RUG tickets
        (rug_repair=True, rug_confirmed=False) never reach this method.

        The factory gate is removed — approval no longer gates factory dispatch.
        Instead, approval gates SO confirmation by the customer.
        """
        self.ensure_one()
        if not self.rug_repair or not self.rug_confirmed:
            raise UserError(_(
                'RUG approval request is only for "Under Warranty - RUG" repair types.'
            ))
        if not self.sale_order:
            raise UserError(_(
                'A quotation (Sale Order) must be created before submitting the RUG approval request.'
            ))
        if self.rug_request_sent:
            raise UserError(_('RUG request has already been sent.'))
        self.write({
            'rug_request_sent': True,
            'rug_approval_status': 'pending',
        })

    def action_approve_rug(self):
        """Approve RUG request (manager only).
        Sets rug_approved=True. Note: rug_confirmed is a related field from
        the ticket type and is NOT set here — it is determined by the type record.
        """
        self.ensure_one()
        if self.rug_approval_status != 'pending':
            raise UserError(_('RUG approval is only possible when status is Pending.'))
        self.write({
            'rug_approval_status': 'approved',
            'rug_approved': True,
        })

    def action_reject_rug(self):
        """Reject RUG request (manager only)."""
        self.ensure_one()
        if self.rug_approval_status != 'pending':
            raise UserError(_('RUG rejection is only possible when status is Pending.'))
        self.write({
            'rug_approval_status': 'rejected',
            'rug_approved': False,
        })

    def action_cancel_ticket(self):
        """Cancel the repair ticket with audit trail."""
        self.ensure_one()
        if self.cancelled:
            raise UserError(_('Ticket is already cancelled.'))
        self.write({
            'cancelled': True,
            'cancelled_date': fields.Datetime.now(),
            'cancelled_by': self.env.uid,
            'cancelled_stage_id': self.stage_id.id,
        })

    def action_reopen_ticket(self):
        """Reopen a cancelled repair ticket."""
        self.ensure_one()
        if not self.cancelled:
            raise UserError(_('Only cancelled tickets can be reopened.'))
        self.write({
            'cancelled': False,
            'reopened_date': fields.Datetime.now(),
            'reopened_by': self.env.uid,
        })

    def action_create_serial_number(self):
        """Create a new stock.lot and link to this ticket.
        Available for all repair types, including 'Without Serial No'.
        For the 'Without Serial No' type, the created serial serves as an
        internal reference for tracking purposes only.
        The previous restriction blocking creation for normal_repair_without_serial_no
        has been removed.
        """
        self.ensure_one()
        if self.repair_serial_created:
            raise UserError(_('Serial number already created for this ticket.'))
        lot = self.env['stock.lot'].create({
            'name': self.name,
            'product_id': self.product_id.id
                          if hasattr(self, 'product_id') else False,
            'company_id': self.company_id.id,
        })
        self.write({
            'repair_serial_no': lot.id,
            'repair_serial_created': True,
        })

    def action_view_pickings(self):
        """Open linked stock pickings (Repair Trans)."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Repair Transfers'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('helpdesk_ticket_id', '=', self.id)],
        }

    def action_plan_intervention(self):
        """Open FSM task for repair intervention planning.

        Guards (FR-014):
        - receive_at_factory must be True (item is physically at factory)
        - repair_reason_id must be set (diagnosis recorded before work starts)

        Sets repair_started_stage_updated = True on success.
        Delegates FSM task creation/view to helpdesk_fsm integration.
        """
        self.ensure_one()
        if not self.receive_at_factory:
            raise UserError(_(
                'Item must be received at factory before planning an intervention.'
            ))
        if not self.repair_reason_id:
            raise UserError(_(
                'Please set a Repair Reason before planning an intervention.'
            ))
        self.write({'repair_started_stage_updated': True})
        return self.action_view_fsm_tasks()
```

---

### 2. helpdesk.stage Extension

```python
class HelpdeskStage(models.Model):
    _inherit = 'helpdesk.stage'

    company_id = fields.Many2one(
        'res.company', string='Company', tracking=True,
        help='Leave empty for global stages visible to all companies.'
    )
```

---

### 3. helpdesk.ticket.type Extension

Four boolean flags identify which of the four repair workflow branches a ticket type belongs to.
The flag combination matrix is:

| Ticket Type Name | is_rug | is_rug_confirmed | is_with_serial_no | is_without_serial_no |
|---|---|---|---|---|
| Repair - Under Warranty - RUG | ✓ | ✓ | — | — |
| Repair - Under Warranty - External not RUG | ✓ | — | — | — |
| Repair - Not Under Warranty (With Serial No) | — | — | ✓ | — |
| Repair - Not Under Warranty (Without Serial No) | — | — | — | ✓ |

```python
class HelpdeskTicketType(models.Model):
    _inherit = 'helpdesk.ticket.type'

    is_rug = fields.Boolean(
        string='RUG', default=False,
        help='True for BOTH Under Warranty subtypes. Activates RUG-specific form buttons.'
    )
    is_rug_confirmed = fields.Boolean(
        string='RUG Confirmed', default=False,
        help='True only for "Under Warranty - RUG". Distinguishes full internal RUG approval '
             'workflow from the External not RUG path. Also controls kanban badge visibility.'
    )
    is_with_serial_no = fields.Boolean(
        string='With Serial No', default=False,
        help='Enable to require serial number tracking on tickets of this type.'
    )
    is_without_serial_no = fields.Boolean(
        string='Without Serial No', default=False,
        help='Enable for non-serialised product repairs. Serial fields hidden on ticket form.'
    )
```

---

### 4. stock.picking Extension

```python
class StockPicking(models.Model):
    _inherit = 'stock.picking'

    helpdesk_ticket_id = fields.Many2one(
        'helpdesk.ticket', string='Repair Ticket',
        ondelete='set null', index=True,
        help='The repair ticket that generated this stock transfer.'
    )
```

---

### 5. stock.location Extension

```python
class StockLocation(models.Model):
    _inherit = 'stock.location'

    users_stock_location = fields.Many2many(
        'res.users',
        relation='stock_location_users_rel',
        column1='location_id',
        column2='user_id',
        string='Permitted Users',
        help='Users allowed to process repairs at this location. '
             'Empty = all users permitted.'
    )
```

---

### 6. Repair Diagnosis Master Data Models

All follow the same structure pattern:

```python
class JinstageRepairSymptomArea(models.Model):
    _name = 'jinstage.repair.symptom.area'
    _description = 'Repair Symptom Area'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code', copy=False)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('code_uniq', 'UNIQUE(code)',
         'Symptom Area code must be unique.'),
    ]


class JinstageRepairSymptomCode(models.Model):
    _name = 'jinstage.repair.symptom.code'
    _description = 'Repair Symptom Code'
    _order = 'symptom_area_id, name'

    name = fields.Char(string='Code Name', required=True, translate=True)
    code = fields.Char(string='Code')
    symptom_area_id = fields.Many2one(
        'jinstage.repair.symptom.area', string='Symptom Area'
    )
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)


class JinstageRepairCondition(models.Model):
    _name = 'jinstage.repair.condition'
    _description = 'Repair Condition'
    _order = 'name'

    name = fields.Char(string='Condition', required=True, translate=True)
    code = fields.Char(string='Code')
    active = fields.Boolean(default=True)


class JinstageRepairDiagnosisArea(models.Model):
    _name = 'jinstage.repair.diagnosis.area'
    _description = 'Repair Diagnosis Area'
    _order = 'name'

    name = fields.Char(string='Name', required=True, translate=True)
    code = fields.Char(string='Code')
    active = fields.Boolean(default=True)


class JinstageRepairDiagnosisCode(models.Model):
    _name = 'jinstage.repair.diagnosis.code'
    _description = 'Repair Diagnosis Code'
    _order = 'diagnosis_area_id, name'

    name = fields.Char(string='Diagnosis', required=True, translate=True)
    code = fields.Char(string='Code')
    diagnosis_area_id = fields.Many2one(
        'jinstage.repair.diagnosis.area', string='Diagnosis Area'
    )
    active = fields.Boolean(default=True)


class JinstageRepairReason(models.Model):
    _name = 'jinstage.repair.reason'
    _description = 'Repair Reason'
    _order = 'name'

    name = fields.Char(string='Reason', required=True, translate=True)
    code = fields.Char(string='Code')
    active = fields.Boolean(default=True)


class JinstageRepairReasonCustomer(models.Model):
    _name = 'jinstage.repair.reason.customer'
    _description = 'Repair Reason (Customer)'
    _order = 'name'

    name = fields.Char(string='Customer Reason', required=True,
                        translate=True)
    code = fields.Char(string='Code')
    active = fields.Boolean(default=True)


class JinstageRepairSubReason(models.Model):
    _name = 'jinstage.repair.sub.reason'
    _description = 'Repair Sub Reason'
    _order = 'repair_reason_id, name'

    name = fields.Char(string='Sub Reason', required=True, translate=True)
    code = fields.Char(string='Code')
    repair_reason_id = fields.Many2one(
        'jinstage.repair.reason', string='Repair Reason'
    )
    active = fields.Boolean(default=True)


class JinstageRepairResolution(models.Model):
    _name = 'jinstage.repair.resolution'
    _description = 'Repair Resolution'
    _order = 'name'

    name = fields.Char(string='Resolution', required=True, translate=True)
    code = fields.Char(string='Code')
    active = fields.Boolean(default=True)
```

---

## User Interface Design

### 1. Helpdesk Ticket Form View Extension

```xml
<!-- File: views/helpdesk_ticket_views.xml -->
<record id="view_helpdesk_ticket_repair_form" model="ir.ui.view">
    <field name="name">helpdesk.ticket.repair.form</field>
    <field name="model">helpdesk.ticket</field>
    <field name="inherit_id" ref="helpdesk.helpdesk_ticket_view_form"/>
    <field name="arch" type="xml">

        <!-- Smart Buttons injection -->
        <xpath expr="//div[@name='button_box']" position="inside">
            <button name="action_view_pickings" type="object"
                    class="oe_stat_button" icon="fa-truck"
                    invisible="picking_count == 0">
                <field name="picking_count" widget="statinfo"
                       string="Repair Trans"/>
            </button>
        </xpath>

        <!-- Header action buttons (before statusbar)
             CORRECT MOVEMENT ORDER: factory first, then sales centre after repair.
        -->
        <xpath expr="//header" position="inside">
            <!-- 1. Create Return Transfer (reverse picking to receive item into repair location) -->
            <button name="action_create_repair_route" type="object"
                    string="Create Return Transfer" class="btn-primary"
                    invisible="picking_count > 0"/>
            <!-- 2. Send to Factory — requires return transfer to exist (picking_count > 0)
                 NO centre prerequisite; item goes directly from intake to factory -->
            <button name="action_send_to_factory" type="object"
                    string="Send to Factory"
                    invisible="send_to_factory == True or picking_count == 0"/>
            <!-- 3. Receive at Factory -->
            <button name="action_receive_at_factory" type="object"
                    string="Receive at Factory"
                    invisible="receive_at_factory == True or send_to_factory == False"/>
            <!-- 4. Plan Intervention — requires receive_at_factory and repair_reason_id -->
            <button name="action_plan_intervention" type="object"
                    string="Plan Intervention"
                    invisible="receive_at_factory == False or repair_started_stage_updated == True"/>
            <!-- 5. Send RUG Request — only for "Under Warranty - RUG" (rug_confirmed=True).
                 Requires sale_order to be set (quotation must exist).
                 "External not RUG" tickets (rug_repair=True, rug_confirmed=False) do NOT show this. -->
            <button name="action_send_rug_request" type="object"
                    string="Send RUG Request"
                    invisible="rug_confirmed == False or rug_request_sent == True"/>
            <!-- 5b. Approve RUG — only for Under Warranty - RUG, request already sent -->
            <button name="action_approve_rug" type="object"
                    string="Approve RUG"
                    invisible="rug_confirmed == False or rug_request_sent == False or rug_approved == True"/>
            <!-- 5c. Reject RUG -->
            <button name="action_reject_rug" type="object"
                    string="Reject RUG"
                    invisible="rug_confirmed == False or rug_request_sent == False or rug_approved == True"/>
            <!-- 6. Send to Sales Centre — after repair completion (receive_at_factory must be True) -->
            <button name="action_send_to_centre" type="object"
                    string="Send to Sales Centre"
                    invisible="send_to_centre == True or receive_at_factory == False"/>
            <!-- 7. Receive at Sales Centre -->
            <button name="action_receive_at_centre" type="object"
                    string="Receive at Sales Centre"
                    invisible="receive_at_centre == True or send_to_centre == False"/>
            <!-- 8. Cancel -->
            <button name="action_cancel_ticket" type="object"
                    string="Cancel"
                    invisible="cancelled == True"/>
            <!-- 9. Reopen -->
            <button name="action_reopen_ticket" type="object"
                    string="Reopen"
                    invisible="cancelled == False"/>
        </xpath>

        <!-- Main Tab: serial, warranty, driver info -->
        <xpath expr="//page[@name='description']" position="before">
            <page string="Repair Info" name="repair_info">
                <group>
                    <group string="Repair Classification">
                        <field name="rug_repair" readonly="1"/>
                        <field name="normal_repair_with_serial_no" readonly="1"/>
                        <field name="normal_repair_without_serial_no" readonly="1"/>
                        <!-- repair_reason_id: required before action_plan_intervention (FR-013) -->
                        <field name="repair_reason_id"/>
                    </group>
                    <group string="Serial Number">
                        <field name="repair_serial_no"/>
                        <!-- Create Serial Number available for ALL types, including Without Serial No.
                             For Without Serial No, the serial is an internal reference only. -->
                        <button name="action_create_serial_number" type="object"
                                string="Create Serial Number"
                                invisible="repair_serial_created == True"
                                class="btn-secondary"/>
                        <field name="repair_serial_created" invisible="1"/>
                        <field name="sn_updated"/>
                    </group>
                </group>
                <group>
                    <group string="Vehicle / Driver">
                        <field name="driver_name"/>
                        <field name="vehicle_details"/>
                    </group>
                    <group string="Financial">
                        <field name="balance_due"/>
                        <field name="unit_price"/>
                        <field name="sales_price"/>
                        <field name="quantity"/>
                    </group>
                </group>
                <group string="Documents">
                    <field name="warranty_card" widget="image"
                           options="{'size': [128, 128]}"/>
                    <field name="related_information" widget="image"
                           options="{'size': [128, 128]}"/>
                </group>
                <group string="Materials">
                    <field name="items" widget="many2many_tags"/>
                </group>
            </page>
        </xpath>

        <!-- Extra Info Tab: locations, flags, status -->
        <xpath expr="//page[@name='extra_info']" position="inside">
            <separator string="Repair Locations"/>
            <group>
                <group>
                    <field name="repair_location"/>
                    <field name="return_receipt_location"/>
                </group>
                <group>
                    <field name="source_location"/>
                    <field name="job_location"/>
                </group>
            </group>
            <separator string="Workflow Status"/>
            <group>
                <group>
                    <field name="quick_repair_status"/>
                    <field name="material_availability"/>
                    <field name="rug_approval_status"
                           invisible="rug_repair == False"/>
                    <field name="stage_date" readonly="1"/>
                </group>
                <group>
                    <field name="send_to_centre"/>
                    <field name="receive_at_centre"/>
                    <field name="send_to_factory"/>
                    <field name="receive_at_factory"/>
                    <field name="handed_over"/>
                    <field name="fsm_task_done" readonly="1"/>
                </group>
            </group>
            <separator string="Sale Order Flags"/>
            <group>
                <group>
                    <field name="sale_order" readonly="1"/>
                    <field name="valid_confirmed_so"/>
                    <field name="valid_delivered_so"/>
                    <field name="valid_invoiced_so"/>
                </group>
                <group>
                    <field name="invoice_stage_updated"/>
                    <field name="repair_started_stage_updated"/>
                    <field name="estimation_approved_stage_updated"/>
                    <field name="balance_due"/>
                </group>
            </group>
            <separator string="Tracking"/>
            <group>
                <group>
                    <field name="s_shipped_by" readonly="1"/>
                    <field name="s_received_by" readonly="1"/>
                    <field name="f_shipped_by" readonly="1"/>
                    <field name="f_received_by" readonly="1"/>
                </group>
            </group>
        </xpath>

        <!-- Cancel/Reopen Log Tab -->
        <xpath expr="//notebook" position="inside">
            <page string="Cancel/Reopen Log" name="cancel_log">
                <group string="Cancellation">
                    <group>
                        <field name="cancelled" readonly="1"/>
                        <field name="cancelled_date" readonly="1"/>
                        <field name="cancelled_by" readonly="1"/>
                        <field name="cancelled_stage_id" readonly="1"/>
                        <field name="cancel_status"/>
                    </group>
                    <group>
                        <field name="cancelled_2"/>
                        <field name="re_estimate_status"/>
                    </group>
                </group>
                <group string="Reopen">
                    <group>
                        <field name="reopened_date" readonly="1"/>
                        <field name="reopened_by" readonly="1"/>
                        <field name="reopen_status"/>
                    </group>
                </group>
                <group string="RUG Approval">
                    <field name="rug_request_sent" readonly="1"
                           invisible="rug_repair == False"/>
                    <field name="rug_approved" readonly="1"
                           invisible="rug_repair == False"/>
                    <field name="rug_confirmed" readonly="1"
                           invisible="rug_repair == False"/>
                </group>
            </page>
        </xpath>

        <!-- Hidden computed fields needed by domain expressions -->
        <xpath expr="//sheet" position="inside">
            <field name="rug_repair" invisible="1"/>
            <field name="normal_repair_with_serial_no" invisible="1"/>
            <field name="normal_repair_without_serial_no" invisible="1"/>
            <field name="picking_count" invisible="1"/>
            <field name="user_location_validation" invisible="1"/>
        </xpath>

    </field>
</record>
```

### 2. Helpdesk Ticket Kanban View Extension

```xml
<record id="view_helpdesk_ticket_repair_kanban" model="ir.ui.view">
    <field name="name">helpdesk.ticket.repair.kanban</field>
    <field name="model">helpdesk.ticket</field>
    <field name="inherit_id" ref="helpdesk.helpdesk_ticket_view_kanban"/>
    <field name="arch" type="xml">
        <xpath expr="//kanban" position="inside">
            <field name="rug_repair"/>
            <field name="rug_confirmed"/>
            <field name="normal_repair_with_serial_no"/>
            <field name="normal_repair_without_serial_no"/>
            <field name="quick_repair_status"/>
            <field name="material_availability"/>
            <field name="rug_approval_status"/>
        </xpath>
        <!-- Inject badge row after existing card content -->
        <xpath expr="//div[hasclass('oe_kanban_details')]" position="inside">
            <div class="o_repair_badges mt-1">
                <!-- Under Warranty - RUG (rug_repair=T, rug_confirmed=T) -->
                <span t-if="record.rug_repair.raw_value and record.rug_confirmed.raw_value"
                      class="badge text-bg-warning me-1">Under Warranty - RUG</span>
                <!-- Under Warranty - External not RUG (rug_repair=T, rug_confirmed=F) -->
                <span t-elif="record.rug_repair.raw_value and not record.rug_confirmed.raw_value"
                      class="badge text-bg-info me-1">Under Warranty - Ext</span>
                <span t-elif="record.normal_repair_with_serial_no.raw_value"
                      class="badge text-bg-success me-1">Not UW - Serial</span>
                <span t-elif="record.normal_repair_without_serial_no.raw_value"
                      class="badge text-bg-secondary me-1">Not UW - No Serial</span>
                <!-- RUG Approval Status badge — only for Under Warranty - RUG type -->
                <span t-if="record.rug_confirmed.raw_value and record.rug_approval_status.value"
                      class="badge text-bg-light me-1">
                    <t t-esc="record.rug_approval_status.value"/>
                </span>
                <span t-if="record.quick_repair_status.value"
                      class="badge text-bg-light">
                    <t t-esc="record.quick_repair_status.value"/>
                </span>
            </div>
        </xpath>
    </field>
</record>
```

### 3. Helpdesk Ticket List View Extension (priority 900)

```xml
<record id="view_helpdesk_ticket_repair_tree" model="ir.ui.view">
    <field name="name">helpdesk.ticket.repair.tree</field>
    <field name="model">helpdesk.ticket</field>
    <field name="inherit_id" ref="helpdesk.helpdesk_tickets_view_list"/>
    <field name="priority">900</field>
    <field name="arch" type="xml">
        <xpath expr="//list" position="attributes">
            <attribute name="decoration-muted">cancelled == True</attribute>
        </xpath>
        <xpath expr="//field[@name='name']" position="after">
            <field name="rug_repair" optional="show"/>
            <field name="normal_repair_with_serial_no" optional="show"/>
            <field name="repair_serial_no" optional="show"/>
            <field name="repair_location" optional="show"/>
        </xpath>
        <xpath expr="//field[@name='stage_id']" position="after">
            <field name="rug_approval_status" optional="show"/>
            <field name="material_availability" optional="show"/>
            <field name="balance_due" optional="show"/>
            <field name="send_to_centre" optional="show"/>
            <field name="receive_at_centre" optional="show"/>
            <field name="send_to_factory" optional="show"/>
            <field name="receive_at_factory" optional="show"/>
            <field name="stage_date" optional="show"/>
        </xpath>
    </field>
</record>
```

### 4. Stage View Extensions

```xml
<!-- File: views/helpdesk_stage_views.xml -->
<record id="view_helpdesk_stage_repair_form" model="ir.ui.view">
    <field name="name">helpdesk.stage.repair.form</field>
    <field name="model">helpdesk.stage</field>
    <field name="inherit_id" ref="helpdesk.helpdesk_stage_view_form"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='name']" position="after">
            <field name="company_id"/>
        </xpath>
    </field>
</record>

<record id="view_helpdesk_stage_repair_tree" model="ir.ui.view">
    <field name="name">helpdesk.stage.repair.tree</field>
    <field name="model">helpdesk.stage</field>
    <field name="inherit_id" ref="helpdesk.helpdesk_stage_view_list"/>
    <field name="arch" type="xml">
        <xpath expr="//field[@name='name']" position="after">
            <field name="company_id" optional="show"/>
        </xpath>
    </field>
</record>
```

### 5. Ticket Type View Extension

```xml
<!-- File: views/helpdesk_ticket_type_views.xml -->
<record id="view_helpdesk_ticket_type_repair_tree" model="ir.ui.view">
    <field name="name">helpdesk.ticket.type.repair.tree</field>
    <field name="model">helpdesk.ticket.type</field>
    <field name="inherit_id" ref="helpdesk.helpdesk_ticket_type_view_list"/>
    <field name="arch" type="xml">
        <!-- Four flag columns matching the repair type matrix:
             Type                          | is_rug | is_rug_confirmed | is_with_serial_no | is_without_serial_no
             Under Warranty - RUG          |   ✓    |        ✓         |        —          |          —
             Under Warranty - Ext not RUG  |   ✓    |        —         |        —          |          —
             Not UW (With Serial No)       |   —    |        —         |        ✓          |          —
             Not UW (Without Serial No)    |   —    |        —         |        —          |          ✓
        -->
        <xpath expr="//list" position="inside">
            <field name="is_rug" optional="show"/>
            <field name="is_rug_confirmed" optional="show"/>
            <field name="is_with_serial_no" optional="show"/>
            <field name="is_without_serial_no" optional="show"/>
        </xpath>
    </field>
</record>
```

### 6. Diagnosis Master Data Views

Each diagnosis model follows this pattern (example for Symptom Area):

```xml
<!-- File: views/diagnosis_views.xml -->
<record id="view_repair_symptom_area_list" model="ir.ui.view">
    <field name="name">jinstage.repair.symptom.area.list</field>
    <field name="model">jinstage.repair.symptom.area</field>
    <field name="arch" type="xml">
        <list string="Symptom Areas" editable="top">
            <field name="name"/>
            <field name="code"/>
            <field name="description"/>
            <field name="active" optional="show"/>
        </list>
    </field>
</record>

<record id="view_repair_symptom_area_form" model="ir.ui.view">
    <field name="name">jinstage.repair.symptom.area.form</field>
    <field name="model">jinstage.repair.symptom.area</field>
    <field name="arch" type="xml">
        <form string="Symptom Area">
            <sheet>
                <group>
                    <field name="name"/>
                    <field name="code"/>
                    <field name="active"/>
                    <field name="description"/>
                </group>
            </sheet>
        </form>
    </field>
</record>
```

---

## Menu XML Structure

```xml
<!-- File: views/menus.xml -->

<!-- Configuration submenus under Helpdesk > Configuration -->
<menuitem id="menu_repair_diagnosis_root"
          name="Repair Diagnosis"
          parent="helpdesk.helpdesk_menu_configuration"
          groups="helpdesk.group_helpdesk_manager"
          sequence="50"/>

<menuitem id="menu_repair_symptom_areas"
          name="Symptom Areas"
          parent="menu_repair_diagnosis_root"
          action="action_repair_symptom_area"
          sequence="10"/>

<menuitem id="menu_repair_symptom_codes"
          name="Symptom Codes"
          parent="menu_repair_diagnosis_root"
          action="action_repair_symptom_code"
          sequence="20"/>

<menuitem id="menu_repair_conditions"
          name="Conditions"
          parent="menu_repair_diagnosis_root"
          action="action_repair_condition"
          sequence="30"/>

<menuitem id="menu_repair_diagnosis_areas"
          name="Diagnosis Areas"
          parent="menu_repair_diagnosis_root"
          action="action_repair_diagnosis_area"
          sequence="40"/>

<menuitem id="menu_repair_diagnosis_codes"
          name="Diagnosis Codes"
          parent="menu_repair_diagnosis_root"
          action="action_repair_diagnosis_code"
          sequence="50"/>

<menuitem id="menu_repair_reasons"
          name="Repair Reason"
          parent="menu_repair_diagnosis_root"
          action="action_repair_reason"
          sequence="60"/>

<menuitem id="menu_repair_reasons_customer"
          name="Repair Reason (Customer)"
          parent="menu_repair_diagnosis_root"
          action="action_repair_reason_customer"
          sequence="70"/>

<menuitem id="menu_repair_sub_reasons"
          name="Repair Sub Reason"
          parent="menu_repair_diagnosis_root"
          action="action_repair_sub_reason"
          sequence="80"/>

<menuitem id="menu_repair_resolutions"
          name="Resolutions"
          parent="menu_repair_diagnosis_root"
          action="action_repair_resolution"
          sequence="90"/>

<menuitem id="menu_repair_stages"
          name="Repair Stages"
          parent="helpdesk.helpdesk_menu_configuration"
          groups="helpdesk.group_helpdesk_manager"
          sequence="60"/>

<!-- Repair Accounts menu under Configuration -->
<menuitem id="menu_repair_accounts"
          name="Repair Accounts"
          parent="helpdesk.helpdesk_menu_configuration"
          groups="helpdesk.group_helpdesk_manager"
          sequence="70"/>

<!-- Reporting menus under Helpdesk > Reporting -->
<menuitem id="menu_repair_job_details"
          name="Repair Job Details"
          parent="helpdesk.helpdesk_menu_reporting"
          action="action_repair_job_details"
          sequence="20"/>

<menuitem id="menu_repair_so_list"
          name="Repair Sales Order List"
          parent="helpdesk.helpdesk_menu_reporting"
          action="action_repair_so_list"
          sequence="30"/>

<!-- Inactive by default: -->
<menuitem id="menu_repair_job_details_rug"
          name="Repair Job Details RUG Only"
          parent="helpdesk.helpdesk_menu_reporting"
          action="action_repair_job_details_rug"
          sequence="40"
          active="0"/>

<menuitem id="menu_customer_letter_report"
          name="Customer Letter Report"
          parent="helpdesk.helpdesk_menu_reporting"
          action="action_customer_letter_report"
          sequence="50"
          active="0"/>
```

---

## Security Model

### ir.model.access.csv

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_repair_symptom_area_user,access_repair_symptom_area_user,model_jinstage_repair_symptom_area,helpdesk.group_helpdesk_user,1,0,0,0
access_repair_symptom_area_manager,access_repair_symptom_area_manager,model_jinstage_repair_symptom_area,helpdesk.group_helpdesk_manager,1,1,1,1
access_repair_symptom_code_user,access_repair_symptom_code_user,model_jinstage_repair_symptom_code,helpdesk.group_helpdesk_user,1,0,0,0
access_repair_symptom_code_manager,access_repair_symptom_code_manager,model_jinstage_repair_symptom_code,helpdesk.group_helpdesk_manager,1,1,1,1
access_repair_condition_user,access_repair_condition_user,model_jinstage_repair_condition,helpdesk.group_helpdesk_user,1,0,0,0
access_repair_condition_manager,access_repair_condition_manager,model_jinstage_repair_condition,helpdesk.group_helpdesk_manager,1,1,1,1
access_repair_diagnosis_area_user,access_repair_diagnosis_area_user,model_jinstage_repair_diagnosis_area,helpdesk.group_helpdesk_user,1,0,0,0
access_repair_diagnosis_area_manager,access_repair_diagnosis_area_manager,model_jinstage_repair_diagnosis_area,helpdesk.group_helpdesk_manager,1,1,1,1
access_repair_diagnosis_code_user,access_repair_diagnosis_code_user,model_jinstage_repair_diagnosis_code,helpdesk.group_helpdesk_user,1,0,0,0
access_repair_diagnosis_code_manager,access_repair_diagnosis_code_manager,model_jinstage_repair_diagnosis_code,helpdesk.group_helpdesk_manager,1,1,1,1
access_repair_reason_user,access_repair_reason_user,model_jinstage_repair_reason,helpdesk.group_helpdesk_user,1,0,0,0
access_repair_reason_manager,access_repair_reason_manager,model_jinstage_repair_reason,helpdesk.group_helpdesk_manager,1,1,1,1
access_repair_reason_customer_user,access_repair_reason_customer_user,model_jinstage_repair_reason_customer,helpdesk.group_helpdesk_user,1,0,0,0
access_repair_reason_customer_manager,access_repair_reason_customer_manager,model_jinstage_repair_reason_customer,helpdesk.group_helpdesk_manager,1,1,1,1
access_repair_sub_reason_user,access_repair_sub_reason_user,model_jinstage_repair_sub_reason,helpdesk.group_helpdesk_user,1,0,0,0
access_repair_sub_reason_manager,access_repair_sub_reason_manager,model_jinstage_repair_sub_reason,helpdesk.group_helpdesk_manager,1,1,1,1
access_repair_resolution_user,access_repair_resolution_user,model_jinstage_repair_resolution,helpdesk.group_helpdesk_user,1,0,0,0
access_repair_resolution_manager,access_repair_resolution_manager,model_jinstage_repair_resolution,helpdesk.group_helpdesk_manager,1,1,1,1
```

### Record Rules (security/record_rules.xml)

```xml
<!-- Helpdesk Stage: multi-company filter -->
<record id="rule_helpdesk_stage_company" model="ir.rule">
    <field name="name">Helpdesk Stage: Company Filter</field>
    <field name="model_id" ref="helpdesk.model_helpdesk_stage"/>
    <field name="global" eval="True"/>
    <field name="domain_force">
        ['|', ('company_id', '=', False),
              ('company_id', 'in', company_ids)]
    </field>
</record>
```

---

## IR Sequence Definition (data/ir_sequence_data.xml)

```xml
<record id="seq_repair" model="ir.sequence">
    <field name="name">Repair Sequence</field>
    <field name="code">repair.seq</field>
    <field name="prefix">REP/%(year)s/</field>
    <field name="padding">5</field>
    <field name="number_increment">1</field>
    <field name="use_date_range">False</field>
    <field name="company_id" eval="False"/>
</record>
```

---

## Automation Rule Design (data/automation_rules.xml)

### Rule 1: Company ID in Stage

```xml
<record id="automation_company_in_stage" model="base.automation">
    <field name="name">Helpdesk Stage: Set Company ID</field>
    <field name="model_id" ref="helpdesk.model_helpdesk_stage"/>
    <field name="trigger">on_write</field>
    <field name="filter_pre_domain">[]</field>
    <field name="state">code</field>
    <field name="active">True</field>
    <field name="code">
company_id = env.context.get('allowed_company_ids',
    [env.user.company_id.id])[0]
company = env['res.company'].browse(company_id)
record.company_id = company.id
    </field>
</record>
```

### Rule 2: Repair Sequence Assignment

```xml
<record id="automation_repair_sequence" model="base.automation">
    <field name="name">Helpdesk Ticket: Assign Repair Sequence</field>
    <field name="model_id" ref="helpdesk.model_helpdesk_ticket"/>
    <field name="trigger">on_create</field>
    <field name="filter_domain">[('name', '=', 'New')]</field>
    <field name="state">code</field>
    <field name="active">True</field>
    <field name="code">
if record.name == 'New':
    seq = env['ir.sequence'].next_by_code('repair.seq')
    record.write({'name': seq})
    </field>
</record>
```

### Rule 3: Location Validation (Inactive)

```xml
<record id="automation_location_validation" model="base.automation">
    <field name="name">Helpdesk Ticket: Location Validation</field>
    <field name="model_id" ref="helpdesk.model_helpdesk_ticket"/>
    <field name="trigger">on_write</field>
    <field name="filter_pre_domain">[('stage_id.sequence', '=', 1)]</field>
    <field name="state">code</field>
    <field name="active">False</field>
    <field name="code">
# Server-side location permission check
loc = record.repair_location
if loc and loc.users_stock_location:
    if env.user not in loc.users_stock_location:
        raise UserError(
            'You do not have permission to process repairs at %s.' % loc.name
        )
    </field>
</record>
```

---

## Report Templates Design

### Report Actions (report/report_actions.xml)

```xml
<!-- 1. Repair Final Notice (EUR A4) -->
<record id="action_report_repair_final_notice" model="ir.actions.report">
    <field name="name">Repair Final Notice</field>
    <field name="model">helpdesk.ticket</field>
    <field name="report_type">qweb-pdf</field>
    <field name="report_name">
        jinstage_helpdesk_repair.report_repair_final_notice
    </field>
    <field name="report_file">
        jinstage_helpdesk_repair.report_repair_final_notice
    </field>
    <field name="paperformat_id" ref="paperformat_eur_a4"/>
    <field name="binding_model_id" ref="helpdesk.model_helpdesk_ticket"/>
    <field name="binding_type">report</field>
</record>

<!-- 2. Repair Receipt (US Letter) -->
<record id="action_report_repair_receipt" model="ir.actions.report">
    <field name="name">Repair Receipt</field>
    <field name="model">helpdesk.ticket</field>
    <field name="report_type">qweb-pdf</field>
    <field name="report_name">
        jinstage_helpdesk_repair.report_repair_receipt
    </field>
    <field name="paperformat_id" ref="base.paperformat_us"/>
    <field name="binding_model_id" ref="helpdesk.model_helpdesk_ticket"/>
    <field name="binding_type">report</field>
</record>

<!-- 3. Repair Status (Default) -->
<record id="action_report_repair_status" model="ir.actions.report">
    <field name="name">Repair Status</field>
    <field name="model">helpdesk.ticket</field>
    <field name="report_type">qweb-pdf</field>
    <field name="report_name">
        jinstage_helpdesk_repair.report_repair_status
    </field>
    <field name="binding_model_id" ref="helpdesk.model_helpdesk_ticket"/>
    <field name="binding_type">report</field>
</record>

<!-- 4. Helpdesk Ticket Report (Default) -->
<record id="action_report_helpdesk_ticket" model="ir.actions.report">
    <field name="name">Helpdesk Ticket Report</field>
    <field name="model">helpdesk.ticket</field>
    <field name="report_type">qweb-pdf</field>
    <field name="report_name">
        jinstage_helpdesk_repair.report_helpdesk_ticket
    </field>
    <field name="binding_model_id" ref="helpdesk.model_helpdesk_ticket"/>
    <field name="binding_type">report</field>
</record>

<!-- 5. Repair Final Notice - Scrappage (US Letter) -->
<record id="action_report_repair_final_notice_scrappage"
        model="ir.actions.report">
    <field name="name">Repair Final Notice - Scrappage</field>
    <field name="model">helpdesk.ticket</field>
    <field name="report_type">qweb-pdf</field>
    <field name="report_name">
        jinstage_helpdesk_repair.report_repair_final_notice_scrappage
    </field>
    <field name="paperformat_id" ref="base.paperformat_us"/>
    <field name="binding_model_id" ref="helpdesk.model_helpdesk_ticket"/>
    <field name="binding_type">report</field>
</record>
```

### Paper Format (report/paper_formats.xml)

```xml
<record id="paperformat_eur_a4" model="report.paperformat">
    <field name="name">European A4</field>
    <field name="default">False</field>
    <field name="format">A4</field>
    <field name="page_height">0</field>
    <field name="page_width">0</field>
    <field name="orientation">Portrait</field>
    <field name="margin_top">10</field>
    <field name="margin_bottom">10</field>
    <field name="margin_left">10</field>
    <field name="margin_right">10</field>
    <field name="header_line">False</field>
    <field name="header_spacing">35</field>
    <field name="dpi">90</field>
</record>
```

### Report Template Structure (example: report_repair_receipt.xml)

```xml
<template id="report_repair_receipt">
    <t t-call="web.html_container">
        <t t-foreach="docs" t-as="doc">
            <t t-call="web.external_layout">
                <div class="page">
                    <h2 class="text-center">Repair Receipt</h2>
                    <div class="row mt-4">
                        <div class="col-6">
                            <strong>Repair Reference:</strong>
                            <span t-field="doc.name"/>
                        </div>
                        <div class="col-6">
                            <strong>Date:</strong>
                            <span t-field="doc.create_date"
                                  t-options='{"widget": "date"}'/>
                        </div>
                    </div>
                    <div class="row mt-2">
                        <div class="col-6">
                            <strong>Customer:</strong>
                            <span t-field="doc.partner_id.name"/>
                        </div>
                        <div class="col-6">
                            <strong>Repair Type:</strong>
                            <span t-if="doc.rug_repair">RUG Repair</span>
                            <span t-elif="doc.normal_repair_with_serial_no">
                                Normal (With Serial)
                            </span>
                            <span t-else="">Normal (No Serial)</span>
                        </div>
                    </div>
                    <t t-if="doc.repair_serial_no">
                        <div class="row mt-2">
                            <div class="col-12">
                                <strong>Serial Number:</strong>
                                <span t-field="doc.repair_serial_no.name"/>
                            </div>
                        </div>
                    </t>
                    <div class="row mt-2">
                        <div class="col-6">
                            <strong>Repair Location:</strong>
                            <span t-field="doc.repair_location.complete_name"/>
                        </div>
                        <div class="col-6">
                            <strong>Balance Due:</strong>
                            <span t-field="doc.balance_due"/>
                        </div>
                    </div>
                    <!-- Signature lines -->
                    <div class="row mt-5">
                        <div class="col-6 text-center">
                            <div
                                style="border-top:1px solid black;width:80%;
                                       margin:0 auto;">Customer Signature</div>
                        </div>
                        <div class="col-6 text-center">
                            <div
                                style="border-top:1px solid black;width:80%;
                                       margin:0 auto;">Received By</div>
                        </div>
                    </div>
                </div>
            </t>
        </t>
    </t>
</template>
```

---

## __manifest__.py Design

```python
{
    'name': 'JinStage Helpdesk Repair Management',
    'version': '17.0.1.0.0',
    'category': 'Helpdesk',
    'summary': 'Extends Helpdesk into a full Repair Management System',
    'description': """
        JinStage Helpdesk Repair Management extends the standard Odoo
        helpdesk module to provide a complete Repair Management System
        with four repair types (Under Warranty - RUG, Under Warranty - External not RUG,
        Not Under Warranty With Serial, Not Under Warranty Without Serial),
        repair routing via stock pickings, full internal RUG approval workflow
        (Under Warranty - RUG only), FSM integration, serial number tracking,
        and five PDF reports.
    """,
    'author': 'Jinasena Pvt Ltd',
    'website': 'https://www.jinasena.com',
    'license': 'LGPL-3',
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
    'data': [
        # Security first
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        # Data
        'data/ir_sequence_data.xml',
        # Views
        'views/helpdesk_ticket_type_views.xml',
        'views/helpdesk_stage_views.xml',
        'views/helpdesk_ticket_views.xml',
        'views/diagnosis_views.xml',
        'views/actions.xml',
        'views/menus.xml',
        # Reports
        'report/paper_formats.xml',
        'report/report_actions.xml',
        'report/report_repair_receipt.xml',
        'report/report_repair_status.xml',
        'report/report_repair_final_notice.xml',
        'report/report_repair_final_notice_scrappage.xml',
        'report/report_helpdesk_ticket.xml',
        # Automation (last, after models are registered)
        'data/automation_rules.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
```

---

## Workflow Design

### Repair Lifecycle State Transitions

```
[Created] → [Return Transfer Created] → [Sent to Factory] → [Received at Factory]
    → [Plan Intervention] → [Repair in Progress]
    → [Estimation Sent] → [Estimation Approved]
    → [50% Advance Invoice] → [Repair Completed]
    → [Balance Invoice] → [Sent to Sales Centre] → [Received at Sales Centre]
    → [Handed Over / Closed]

RUG Branch (after Quotation Created, before Customer SO Confirmation):
[Repair in Progress / Quotation Created] → [RUG Request Sent] → [RUG Pending Approval]
    → [RUG Approved] → [Customer Confirms SO] → [50% Advance Invoice] → ...

Cancel Path (any active state):
[Any Active State] → [Cancelled]
    → [Reopened] → [Previous Active State]
```

**Key design decisions:**
- Factory comes FIRST (directly after return transfer intake), not after the sales centre.
- Sales centre comes LAST (after repair completion), as the final dispatch before customer handover.
- RUG approval gates SO confirmation, not factory dispatch.
- Plan Intervention requires both `receive_at_factory = True` and `repair_reason_id` set.

---

## Performance Considerations

### Database Indexes

The following fields have `index=True` to support list view sorting and domain filtering:
- `helpdesk.ticket.rug_repair` (stored computed — auto-indexed)
- `helpdesk.ticket.normal_repair_with_serial_no` (stored computed)
- `helpdesk.ticket.cancelled`
- `stock.picking.helpdesk_ticket_id`

### Stored vs Computed Fields

Stored computed fields (for performance in list/search):
- `rug_repair`, `normal_repair_with_serial_no`, `normal_repair_without_serial_no`
- `sale_order`

Non-stored computed fields (real-time, user-context dependent):
- `user_location_validation` (depends on `env.user`)
- `fsm_task_done` (volatile FSM state)
- `picking_ids`, `picking_count` (dynamic search)

### Query Optimisation

```python
# Efficient picking count using search_count
def _compute_picking_ids(self):
    for ticket in self:
        pickings = self.env['stock.picking'].search([
            ('helpdesk_ticket_id', '=', ticket.id)
        ])
        ticket.picking_ids = pickings
        ticket.picking_count = len(pickings)
```

---

## Testing Strategy

### Unit Tests (tests/test_repair_workflow.py)

```python
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError


class TestRepairWorkflow(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create ticket type: Under Warranty - RUG (full internal approval)
        cls.rug_type = cls.env['helpdesk.ticket.type'].create({
            'name': 'Repair - Under Warranty - RUG',
            'is_rug': True,
            'is_rug_confirmed': True,
        })
        # Create ticket type: Under Warranty - External not RUG (no approval)
        cls.external_rug_type = cls.env['helpdesk.ticket.type'].create({
            'name': 'Repair - Under Warranty - External not RUG',
            'is_rug': True,
            'is_rug_confirmed': False,
        })
        # Create ticket type: Not Under Warranty - With Serial No
        cls.serial_type = cls.env['helpdesk.ticket.type'].create({
            'name': 'Repair - Not Under Warranty (With Serial No)',
            'is_with_serial_no': True,
        })
        # Create ticket type: Not Under Warranty - Without Serial No
        cls.no_serial_type = cls.env['helpdesk.ticket.type'].create({
            'name': 'Repair - Not Under Warranty (Without Serial No)',
            'is_without_serial_no': True,
        })
        cls.partner = cls.env.ref('base.res_partner_1')

    def test_rug_repair_classification(self):
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test RUG',
            'partner_id': self.partner.id,
            'ticket_type_id': self.rug_type.id,
        })
        # "Under Warranty - RUG": rug_repair=T, rug_confirmed=T
        self.assertTrue(ticket.rug_repair)
        self.assertTrue(ticket.rug_confirmed)
        self.assertFalse(ticket.normal_repair_with_serial_no)
        self.assertFalse(ticket.normal_repair_without_serial_no)

    def test_external_not_rug_classification(self):
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test External not RUG',
            'partner_id': self.partner.id,
            'ticket_type_id': self.external_rug_type.id,
        })
        # "Under Warranty - External not RUG": rug_repair=T, rug_confirmed=F
        self.assertTrue(ticket.rug_repair)
        self.assertFalse(ticket.rug_confirmed)

    def test_cancel_audit_trail(self):
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test Cancel',
            'partner_id': self.partner.id,
        })
        ticket.action_cancel_ticket()
        self.assertTrue(ticket.cancelled)
        self.assertEqual(ticket.cancelled_by, self.env.user)
        self.assertIsNotNone(ticket.cancelled_date)

    def test_send_to_factory_requires_return_transfer(self):
        # action_send_to_factory requires picking_count > 0 (return transfer must exist)
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test Factory No Transfer',
            'partner_id': self.partner.id,
            'ticket_type_id': self.rug_type.id,
        })
        # No picking created yet — should raise UserError
        with self.assertRaises(UserError):
            ticket.action_send_to_factory()

    def test_send_to_centre_requires_receive_at_factory(self):
        # action_send_to_centre requires receive_at_factory = True
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test Centre Before Factory',
            'partner_id': self.partner.id,
            'ticket_type_id': self.rug_type.id,
        })
        # Factory not complete — should raise UserError
        with self.assertRaises(UserError):
            ticket.action_send_to_centre()

    def test_plan_intervention_requires_repair_reason(self):
        # action_plan_intervention requires repair_reason_id to be set
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test Plan No Reason',
            'partner_id': self.partner.id,
            'ticket_type_id': self.rug_type.id,
        })
        ticket.write({'receive_at_factory': True})
        # No repair_reason_id — should raise UserError
        with self.assertRaises(UserError):
            ticket.action_plan_intervention()

    def test_rug_request_requires_sale_order(self):
        # action_send_rug_request requires sale_order to be set
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test RUG No SO',
            'partner_id': self.partner.id,
            'ticket_type_id': self.rug_type.id,
        })
        # No sale_order — should raise UserError
        with self.assertRaises(UserError):
            ticket.action_send_rug_request()

    def test_external_not_rug_no_approval_required(self):
        # "External not RUG" (rug_confirmed=False) can reach factory without approval
        # Factory only requires picking_count > 0 — no RUG gate
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test External not RUG Factory',
            'partner_id': self.partner.id,
            'ticket_type_id': self.external_rug_type.id,
        })
        # Simulate picking exists
        ticket.write({'picking_id': self.env['stock.picking'].create({
            'picking_type_id': self.env.ref('stock.picking_type_in').id,
            'location_id': self.env.ref('stock.stock_location_customers').id,
            'location_dest_id': self.env.ref('stock.stock_location_stock').id,
            'helpdesk_ticket_id': ticket.id,
        }).id})
        # Should NOT raise UserError — no approval required for this type
        ticket.action_send_to_factory()
        self.assertTrue(ticket.send_to_factory)

    def test_reopen_cancelled_ticket(self):
        ticket = self.env['helpdesk.ticket'].create({
            'name': 'Test Reopen',
            'partner_id': self.partner.id,
        })
        ticket.action_cancel_ticket()
        ticket.action_reopen_ticket()
        self.assertFalse(ticket.cancelled)
        self.assertEqual(ticket.reopened_by, self.env.user)
```

---

## Deployment Checklist

### Pre-deployment Validation
- [ ] All unit tests pass (`python -m pytest addons/jinstage_helpdesk_repair/tests/`)
- [ ] Module installs on fresh Odoo 17 Enterprise database
- [ ] No `x_studio_` field references
- [ ] No deprecated API usage (`attrs=`, `@api.multi`, etc.)
- [ ] All five PDF reports generate without error
- [ ] RUG approval workflow tested end-to-end
- [ ] Cancel/Reopen audit trail verified

### Post-deployment Monitoring
- [ ] Repair sequence generating correctly
- [ ] Company stage automation rule active
- [ ] Location validation automation rule inactive (activate if needed)
- [ ] All 5 report actions visible under Print menu on ticket form

---

**Last Updated:** 2026-04-08
**Document Version:** 1.0
**Approval Status:** Draft
