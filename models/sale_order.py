from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    quotation_type = fields.Selection([
        ('repair', 'Repair'),
        ('sales', 'Sales'),
    ], string='Quotation Type', default='repair')

    order_payment_type = fields.Selection([
        ('cash', 'Cash'),
        ('credit', 'Credit'),
    ], string='Order Payment Type')

    repair_task_id = fields.Many2one('project.task', string='Task', ondelete='set null')

    rug_confirmed = fields.Boolean(string='RUG Confirmed', default=False)
    rug_approved = fields.Boolean(string='RUG Approved', default=False)
    re_estimate_request_count = fields.Integer(string='Re-estimate Request Count', default=0)
    re_estimate_count = fields.Integer(string='Re-estimate Count', default=0)
    reject_reason = fields.Char(string='Reject Reason')
    repair_reason_id = fields.Many2one('jinstage.repair.reason', string='Repair Reason')

    # --- Credit Limit Details ---
    credit_limit_amount = fields.Float(string='Credit Limit', default=0.0)
    credit_outstanding = fields.Float(string='Outstanding Amount', default=0.0)
    credit_limit_approved = fields.Boolean(string='Credit Limit Approved', default=False)
    credit_limit_request_sent = fields.Boolean(string='Credit Limit Request Sent', default=False)

    # --- Repair Image tab ---
    repair_image_01 = fields.Binary(string='Repair Image 01', attachment=True)
    repair_image_02 = fields.Binary(string='Repair Image 02', attachment=True)

    # --- Warranty Details tab ---
    warranty_card = fields.Binary(string='Warranty Card', attachment=True)
    related_information = fields.Binary(string='Related Information', attachment=True)

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def action_request_rug_approval(self):
        """Request RUG approval — delegates to the linked helpdesk ticket."""
        self.ensure_one()
        ticket = self._get_linked_ticket()
        if not ticket:
            raise UserError(_('No repair ticket is linked to this sale order.'))
        ticket.action_send_rug_request()

    def _get_linked_ticket(self):
        """Return the helpdesk ticket linked through the repair task."""
        if self.repair_task_id and hasattr(self.repair_task_id, 'helpdesk_ticket_ids'):
            return self.repair_task_id.helpdesk_ticket_ids[:1]
        # Fallback: search directly
        return self.env['helpdesk.ticket'].search([('sale_order', '=', self.id)], limit=1)
