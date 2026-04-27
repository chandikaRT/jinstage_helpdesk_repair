from odoo import _, api, fields, models
from odoo.exceptions import UserError


class HelpdeskTicket(models.Model):
    _inherit = 'helpdesk.ticket'

    # =========================================================================
    # REPAIR TYPE CLASSIFICATION
    # Four repair types distinguished by ticket type flags:
    #   Under Warranty - RUG:         rug_repair=T, rug_confirmed=T
    #   Under Warranty - External:    rug_repair=T, rug_confirmed=F
    #   Not UW With Serial:           normal_repair_with_serial_no=T
    #   Not UW Without Serial:        normal_repair_without_serial_no=T
    # =========================================================================
    rug_repair = fields.Boolean(
        related='ticket_type_id.is_rug', store=True, string='RUG Repair'
    )
    rug_confirmed = fields.Boolean(
        related='ticket_type_id.is_rug_confirmed', store=True, string='RUG Confirmed'
    )
    normal_repair_with_serial_no = fields.Boolean(
        related='ticket_type_id.is_with_serial_no', store=True,
        string='Normal Repair (With Serial)'
    )
    normal_repair_without_serial_no = fields.Boolean(
        related='ticket_type_id.is_without_serial_no', store=True,
        string='Normal Repair (No Serial)'
    )

    # --- Identification & Tracking ---
    repair_serial_no = fields.Many2one('stock.lot', string='Serial Number')
    serial_number = fields.Many2one('stock.lot', string='Serial Number (Alt)')
    repair_reason_id = fields.Many2one(
        'jinstage.repair.reason', string='Repair Reason', tracking=True
    )
    repair_reason_ids = fields.Many2many(
        'jinstage.repair.reason',
        relation='helpdesk_ticket_repair_reason_rel',
        column1='ticket_id', column2='reason_id',
        string='Repair Reasons', tracking=True
    )
    customer_type = fields.Selection([
        ('cash', 'Cash Customer'),
        ('credit', 'Credit Customer'),
    ], string='Customer Type', tracking=True)
    picking_id = fields.Many2one('stock.picking', string='Picking', ondelete='set null')
    sale_order = fields.Many2one(
        'sale.order', string='Sale Order',
        compute='_compute_sale_order', store=False
    )
    driver_name = fields.Char(string='Driver Name')
    vehicle_details = fields.Char(string='Vehicle Details')

    # --- Location Management ---
    repair_location = fields.Many2one(
        'stock.location', string='Repair Location',
        domain="[('usage', 'in', ['internal', 'transit'])]"
    )
    return_receipt_location = fields.Many2one('stock.location', string='Return Receipt Location')
    source_location = fields.Many2one('stock.location', string='Source Location')
    job_location = fields.Many2one('stock.location', string='Job Location')

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
        ('pending', 'Pending RUG Approval'),
        ('approved', 'RUG Approved'),
        ('rejected', 'RUG Rejected'),
    ], string='RUG Approval Status', tracking=True)

    material_availability = fields.Selection([
        ('available', 'Available'),
        ('partial', 'Partially Available'),
        ('unavailable', 'Unavailable'),
        ('ordered', 'Ordered'),
    ], string='Material Availability', tracking=True)

    # --- Stage Tracking ---
    stage_date = fields.Datetime(string='Stage Changed Date', tracking=True)
    cancelled_date = fields.Datetime(string='Cancelled Date')
    reopened_date = fields.Datetime(string='Reopened Date')
    cancelled_stage_id = fields.Many2one('helpdesk.stage', string='Stage at Cancellation')

    # --- Boolean Workflow Flags ---
    send_to_centre = fields.Boolean(string='Send to Centre', default=False)
    receive_at_centre = fields.Boolean(string='Receive at Centre', default=False)
    send_to_factory = fields.Boolean(string='Send to Factory', default=False)
    receive_at_factory = fields.Boolean(string='Receive at Factory', default=False)
    handed_over = fields.Boolean(string='Handed Over', default=False, readonly=True)
    fsm_task_done = fields.Boolean(
        string='FSM Task Done', compute='_compute_fsm_task_done', store=False
    )
    cancelled = fields.Boolean(string='Cancelled', default=False, tracking=True)
    cancelled_2 = fields.Boolean(string='Cancelled (Stage 2)', default=False)
    repair_serial_created = fields.Boolean(string='Repair Serial Created', default=False)
    sn_updated = fields.Boolean(string='Serial Number Updated', default=False)
    rug_approved = fields.Boolean(string='RUG Approved', default=False, tracking=True)
    rug_request_sent = fields.Boolean(string='RUG Request Sent', default=False, tracking=True)
    valid_confirmed_so = fields.Boolean(string='SO Confirmed', default=False)
    valid_confirmed2_so = fields.Boolean(string='SO Confirmed (2)', default=False)
    valid_delivered_so = fields.Boolean(string='SO Delivered', default=False)
    valid_invoiced_so = fields.Boolean(string='SO Invoiced', default=False)
    repair_started_stage_updated = fields.Boolean(string='Repair Started Stage Updated', default=False)
    estimation_approved_stage_updated = fields.Boolean(string='Estimation Approved Stage Updated', default=False)
    invoice_stage_updated = fields.Boolean(string='Invoice Stage Updated', default=False)
    user_location_validation = fields.Boolean(
        string='User Location Valid', compute='_compute_user_location_validation', store=False
    )
    tested_ok = fields.Boolean(string='Tested OK', default=False, tracking=True)
    image_uploaded = fields.Boolean(string='Image Uploaded', default=False)
    diagnosis_validated = fields.Boolean(string='Diagnosis Validated', default=False)
    dispatch_done = fields.Boolean(string='Dispatched', default=False, readonly=True, tracking=True)
    credit_limit_request_sent = fields.Boolean(string='Credit Limit Request Sent', default=False)
    credit_limit_approved = fields.Boolean(string='Credit Limit Approved', default=False)
    rug_repriced = fields.Boolean(string='RUG Repriced to Standard', default=False)
    advance_invoice_created = fields.Boolean(string='Advance Invoice Created', default=False)
    insufficient_inventory = fields.Boolean(
        string='Insufficient Inventory',
        compute='_compute_insufficient_inventory', store=False
    )

    # --- Quotation & Financial Dates ---
    quotation_expiry_date = fields.Date(string='Quotation Expiry Date', tracking=True)

    # --- Audit & User Tracking ---
    cancelled_by = fields.Many2one('res.users', string='Cancelled By')
    reopened_by = fields.Many2one('res.users', string='Reopened By')
    s_received_by = fields.Many2one('res.users', string='Received By (Centre)')
    f_received_by = fields.Many2one('res.users', string='Received By (Factory)')
    s_shipped_by = fields.Many2one('res.users', string='Shipped By (Centre)')
    f_shipped_by = fields.Many2one('res.users', string='Shipped By (Factory)')
    created_by_1 = fields.Many2one('res.users', string='Created By 1')
    created_by_2 = fields.Many2one('res.users', string='Created By 2')
    created_by_3 = fields.Many2one('res.users', string='Created By 3')
    created_by_4 = fields.Many2one('res.users', string='Created By 4')
    created_by_5 = fields.Many2one('res.users', string='Created By 5')
    created_by_6 = fields.Many2one('res.users', string='Created By 6')
    created_by_7 = fields.Many2one('res.users', string='Created By 7')
    created_by_8 = fields.Many2one('res.users', string='Created By 8')
    created_by_9 = fields.Many2one('res.users', string='Created By 9')
    created_by_10 = fields.Many2one('res.users', string='Created By 10')

    # --- Financial & Product Fields ---
    balance_due = fields.Float(string='Balance Due', default=0.0)
    sales_price = fields.Char(string='Sales Price')
    unit_price = fields.Float(string='Unit Price', default=0.0)
    quantity = fields.Integer(string='Quantity', default=1)
    qty = fields.Char(string='Qty')
    items = fields.Many2many(
        'product.product',
        relation='helpdesk_ticket_product_rel',
        column1='ticket_id', column2='product_id',
        string='Items'
    )

    # --- Document & Image Fields ---
    warranty_card = fields.Binary(string='Warranty Card', attachment=True)
    related_information = fields.Binary(string='Related Information', attachment=True)

    # --- Picking Smart Button ---
    picking_ids = fields.Many2many(
        'stock.picking', compute='_compute_picking_ids', string='Pickings'
    )
    picking_count = fields.Integer(compute='_compute_picking_ids', string='Picking Count')

    # =========================================================================
    # ORM OVERRIDES
    # =========================================================================

    def write(self, vals):
        if 'stage_id' in vals:
            vals['stage_date'] = fields.Datetime.now()
        return super().write(vals)

    # =========================================================================
    # COMPUTED FIELDS
    # =========================================================================

    @api.depends()
    def _compute_fsm_task_done(self):
        has_task_ids = 'task_ids' in self.env['helpdesk.ticket']._fields
        for ticket in self:
            if not has_task_ids:
                ticket.fsm_task_done = False
                continue
            tasks = ticket.task_ids
            ticket.fsm_task_done = bool(tasks) and all(
                t.stage_id.is_closed for t in tasks
            )

    @api.depends()
    def _compute_sale_order(self):
        has_task_ids = 'task_ids' in self.env['helpdesk.ticket']._fields
        for ticket in self:
            if not has_task_ids:
                ticket.sale_order = False
                continue
            sale_orders = ticket.task_ids.mapped('sale_order_id')
            ticket.sale_order = sale_orders[:1] if sale_orders else False

    def _compute_user_location_validation(self):
        for ticket in self:
            loc = ticket.repair_location
            if not loc or not loc.users_stock_location:
                ticket.user_location_validation = True
            else:
                ticket.user_location_validation = self.env.user in loc.users_stock_location

    def _compute_insufficient_inventory(self):
        for ticket in self:
            if not ticket.items or not ticket.repair_location:
                ticket.insufficient_inventory = False
                continue
            warehouse = self.env['stock.warehouse'].search(
                [('lot_stock_id', '=', ticket.repair_location.id)], limit=1
            )
            if not warehouse:
                ticket.insufficient_inventory = False
                continue
            location = warehouse.lot_stock_id
            insufficient = False
            for product in ticket.items:
                quant = self.env['stock.quant'].search([
                    ('product_id', '=', product.id),
                    ('location_id', 'child_of', location.id),
                ], limit=1)
                if not quant or quant.quantity < 1:
                    insufficient = True
                    break
            ticket.insufficient_inventory = insufficient

    @api.depends('picking_id', 'picking_id.helpdesk_ticket_id')
    def _compute_picking_ids(self):
        for ticket in self:
            pickings = self.env['stock.picking'].search([
                ('helpdesk_ticket_id', '=', ticket.id)
            ])
            ticket.picking_ids = pickings
            ticket.picking_count = len(pickings)

    # =========================================================================
    # ONCHANGE
    # =========================================================================

    @api.onchange('ticket_type_id')
    def _onchange_ticket_type_id(self):
        """Clear serial number when changing to a non-serial repair type."""
        if self.ticket_type_id and not self.ticket_type_id.is_with_serial_no:
            self.repair_serial_no = False

    @api.onchange('repair_serial_no')
    def _onchange_repair_serial_no(self):
        """Mark serial number as updated when changed on existing record."""
        if self._origin.repair_serial_no and self.repair_serial_no != self._origin.repair_serial_no:
            self.sn_updated = True

    # =========================================================================
    # SERIAL NUMBER MANAGEMENT (FR-003)
    # =========================================================================

    def action_create_serial_number(self):
        """Create a new stock.lot serial number for this repair ticket.
        - For 'Without Serial No' type: uses repair.temp.serial sequence (REP/SER/YYYY/NNN)
        - For all other types: uses the ticket name as the lot name
        """
        self.ensure_one()
        if self.repair_serial_created:
            raise UserError(_('A serial number has already been created for this ticket.'))
        if self.normal_repair_without_serial_no:
            serial_name = self.env['ir.sequence'].next_by_code('repair.temp.serial') or self.name
        else:
            serial_name = self.name
        lot = self.env['stock.lot'].create({
            'name': serial_name,
            'company_id': self.company_id.id or self.env.company.id,
            'product_id': self.items[:1].id if self.items else False,
        })
        self.write({
            'repair_serial_no': lot.id,
            'repair_serial_created': True,
            'sn_updated': True,
        })

    # =========================================================================
    # CANCEL & REOPEN (FR-008)
    # =========================================================================

    def action_cancel_ticket(self):
        """Cancel the repair ticket with full audit trail.
        If cancellation reason is 'customer_request' at quotation stage,
        ticket moves to 'Repair Completed' (physical return still needed).
        """
        self.ensure_one()
        if self.cancelled:
            raise UserError(_('This ticket is already cancelled.'))
        vals = {
            'cancelled': True,
            'cancelled_date': fields.Datetime.now(),
            'cancelled_by': self.env.uid,
            'cancelled_stage_id': self.stage_id.id,
        }
        # Customer declined quotation → move to Repair Completed for physical return
        if self.cancel_status == 'customer_request' and self.sale_order:
            completed_stage = self.env['helpdesk.stage'].search(
                [('name', 'ilike', 'Repair Completed')], limit=1
            )
            if completed_stage:
                vals['stage_id'] = completed_stage.id
        self.write(vals)

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

    # =========================================================================
    # RUG APPROVAL WORKFLOW (FR-007)
    # =========================================================================

    def action_send_rug_request(self):
        """Send RUG approval request.
        Only for 'Under Warranty - RUG' (rug_repair=True AND rug_confirmed=True).
        'External not RUG' (rug_confirmed=False) bypasses approval entirely.
        Per workflow: approval is requested AFTER the quotation is created (products added
        at factory), BEFORE the customer confirms the sale order.
        """
        self.ensure_one()
        if not self.rug_repair or not self.rug_confirmed:
            raise UserError(_(
                'RUG approval request is only for "Under Warranty - RUG" repair types.'
            ))
        if not self.sale_order:
            raise UserError(_(
                'A quotation must be created (add repair items via Plan Intervention) '
                'before requesting RUG approval.'
            ))
        if self.rug_request_sent:
            raise UserError(_('RUG approval request has already been sent.'))
        self.write({
            'rug_request_sent': True,
            'rug_approval_status': 'pending',
        })

    def action_approve_rug(self):
        """Approve RUG request. Note: rug_confirmed is a related field from ticket type,
        NOT set here — it is determined by which ticket type record is selected.
        """
        self.ensure_one()
        if self.rug_approval_status != 'pending':
            raise UserError(_('RUG approval is only possible when status is Pending.'))
        self.write({
            'rug_approval_status': 'approved',
            'rug_approved': True,
        })

    def action_reject_rug(self):
        """Reject RUG request. Pricing must be updated to standard repair rates."""
        self.ensure_one()
        if self.rug_approval_status != 'pending':
            raise UserError(_('RUG rejection is only possible when status is Pending.'))
        self.write({
            'rug_approval_status': 'rejected',
            'rug_approved': False,
        })
        self.message_post(
            body=_('RUG approval rejected. Pricing must be updated to standard repair rates '
                   'before proceeding. Please update the quotation and resubmit.')
        )

    # =========================================================================
    # REPAIR ROUTE & STOCK PICKING (FR-005)
    # =========================================================================

    def action_create_repair_route(self):
        """Create stock picking records for the repair route."""
        self.ensure_one()
        if self.picking_count > 0:
            raise UserError(_('Repair route has already been created for this ticket.'))
        if not self.repair_location:
            raise UserError(_('Please assign a Repair Location before creating the repair route.'))
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('warehouse_id.lot_stock_id', '=', self.repair_location.id),
        ], limit=1)
        if not picking_type:
            picking_type = self.env['stock.picking.type'].search([
                ('code', '=', 'incoming'),
            ], limit=1)
        picking = self.env['stock.picking'].create({
            'picking_type_id': picking_type.id,
            'location_id': self.source_location.id or self.env.ref('stock.stock_location_customers').id,
            'location_dest_id': self.repair_location.id,
            'origin': self.name,
            'helpdesk_ticket_id': self.id,
        })
        self.write({'picking_id': picking.id})

    def action_view_pickings(self):
        """Open filtered list of stock pickings for this ticket."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Repair Pickings'),
            'res_model': 'stock.picking',
            'view_mode': 'list,form',
            'domain': [('helpdesk_ticket_id', '=', self.id)],
            'context': {'default_helpdesk_ticket_id': self.id},
        }

    def action_view_fsm_tasks(self):
        """Open FSM tasks linked to this ticket."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('FSM Tasks'),
            'res_model': 'project.task',
            'view_mode': 'list,form',
            'domain': [('helpdesk_ticket_ids', 'in', [self.id])],
        }

    # =========================================================================
    # CENTRE / FACTORY TRANSFER TRACKING (FR-006)
    # =========================================================================

    def action_send_to_factory(self):
        """Mark item as dispatched to factory.
        This is the first movement step after creating the repair route.
        No approval gate here — RUG approval happens after the quotation is created.
        """
        self.ensure_one()
        if not self.picking_count:
            raise UserError(_('Please create the return transfer before sending to factory.'))
        self.write({
            'send_to_factory': True,
            'f_shipped_by': self.env.uid,
            'stage_date': fields.Datetime.now(),
        })

    def action_receive_at_factory(self):
        """Mark item as received at factory."""
        self.ensure_one()
        if not self.send_to_factory:
            raise UserError(_('Item has not been sent to factory yet.'))
        if self.receive_at_factory:
            raise UserError(_('Item has already been received at factory.'))
        self.write({
            'receive_at_factory': True,
            'f_received_by': self.env.uid,
            'stage_date': fields.Datetime.now(),
        })

    def action_send_to_centre(self):
        """Mark repaired item as dispatched back to the sales centre.
        This happens AFTER factory repair work is completed.
        """
        self.ensure_one()
        if not self.receive_at_factory:
            raise UserError(_(
                'Item must be received at factory and repair completed before '
                'sending back to the sales centre.'
            ))
        self.write({
            'send_to_centre': True,
            's_shipped_by': self.env.uid,
            'stage_date': fields.Datetime.now(),
        })

    def action_receive_at_centre(self):
        """Mark repaired item as received at sales centre (final leg before handover)."""
        self.ensure_one()
        if not self.send_to_centre:
            raise UserError(_('Item has not been sent to centre yet.'))
        if self.receive_at_centre:
            raise UserError(_('Item has already been received at centre.'))
        self.write({
            'receive_at_centre': True,
            's_received_by': self.env.uid,
            'stage_date': fields.Datetime.now(),
        })

    def action_plan_intervention(self):
        """Activate FSM task for repair work at factory.
        Repair reason is mandatory before proceeding.
        Guards: item must be received at factory; repair reason must be set.
        """
        self.ensure_one()
        if not self.receive_at_factory:
            raise UserError(_('Item must be received at factory before planning intervention.'))
        if not self.repair_reason_ids and not self.repair_reason_id:
            raise UserError(_(
                'Repair Reason is required before planning the intervention. '
                'Please set the Repair Reason field.'
            ))
        if not self.image_uploaded:
            raise UserError(_(
                'At least one pump image must be uploaded before planning the intervention. '
                'Please upload an image in the Related Information or Warranty Card field.'
            ))
        self.write({'repair_started_stage_updated': True})
        has_task_ids = 'task_ids' in self.env['helpdesk.ticket']._fields
        return {
            'type': 'ir.actions.act_window',
            'name': _('Repair Tasks'),
            'res_model': 'project.task',
            'view_mode': 'tree,form',
            'domain': [('helpdesk_ticket_ids', 'in', [self.id])] if has_task_ids else [],
            'context': {
                'default_helpdesk_ticket_ids': [(4, self.id)] if has_task_ids else [],
                'default_is_fsm': True,
            },
        }

    def action_tested_ok(self):
        """Mark repair as Tested OK — no parts needed, no charge.
        Bypasses quotation and invoicing. Dispatch enabled immediately.
        """
        self.ensure_one()
        if not self.receive_at_factory:
            raise UserError(_('Item must be received at factory before marking as Tested OK.'))
        if self.tested_ok:
            raise UserError(_('This ticket has already been marked as Tested OK.'))
        # Find the "Repair Completed" stage
        completed_stage = self.env['helpdesk.stage'].search(
            [('name', 'ilike', 'Repair Completed')], limit=1
        )
        vals = {
            'tested_ok': True,
            'handed_over': False,
        }
        if completed_stage:
            vals['stage_id'] = completed_stage.id
        self.write(vals)

    def action_dispatch(self):
        """Final dispatch — return repaired item to customer.
        Payment gate:
        - Tested OK repairs: no payment required.
        - Cash customers: full invoice must be paid (valid_invoiced_so = True).
        - Credit customers: invoice must be generated (valid_invoiced_so = True).
        """
        self.ensure_one()
        if not self.receive_at_centre and not self.tested_ok:
            raise UserError(_(
                'Item must be received at the sales centre before dispatch, '
                'unless the repair was marked as Tested OK.'
            ))
        if not self.tested_ok and not self.valid_invoiced_so:
            raise UserError(_(
                'The invoice must be fully paid before dispatch is enabled.'
            ))
        # Create return picking to customer
        customer_location = self.env.ref('stock.stock_location_customers')
        source_loc = self.repair_location or self.return_receipt_location
        if not source_loc:
            raise UserError(_('Repair Location must be set to create a dispatch transfer.'))
        picking_type = self.env['stock.picking.type'].search([
            ('code', '=', 'outgoing'),
        ], limit=1)
        if picking_type:
            self.env['stock.picking'].create({
                'picking_type_id': picking_type.id,
                'location_id': source_loc.id,
                'location_dest_id': customer_location.id,
                'origin': self.name,
                'helpdesk_ticket_id': self.id,
            })
        self.write({
            'dispatch_done': True,
            'handed_over': True,
            'stage_date': fields.Datetime.now(),
        })

    def action_request_credit_limit(self):
        """Request Finance Department approval for credit limit override."""
        self.ensure_one()
        if self.customer_type != 'credit':
            raise UserError(_('Credit limit approval is only for credit customers.'))
        if self.credit_limit_request_sent:
            raise UserError(_('Credit limit approval request has already been sent.'))
        self.write({'credit_limit_request_sent': True})

    def action_approve_credit_limit(self):
        """Approve credit limit override — Finance/Accounts Dept only."""
        self.ensure_one()
        if not self.credit_limit_request_sent:
            raise UserError(_('No credit limit approval request has been sent.'))
        self.write({'credit_limit_approved': True})
