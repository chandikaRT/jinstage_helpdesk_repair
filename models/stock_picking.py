from odoo import api, fields, models


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    helpdesk_ticket_id = fields.Many2one(
        'helpdesk.ticket', string='Repair Ticket',
        ondelete='set null', index=True,
        help='The repair ticket that generated this stock transfer.'
    )
    created_from_help_ticket = fields.Many2one(
        'helpdesk.ticket', string='Created from Help Ticket',
        ondelete='set null', index=True,
    )
    ticket_sale_order_id = fields.Many2one(
        'sale.order', string='Ticket Sales Order',
        compute='_compute_ticket_sale_order', store=False
    )
    quotation_type = fields.Char(
        string='Quotation Type', compute='_compute_ticket_sale_order', store=False
    )
    validation_note = fields.Char(string='Validation')

    @api.depends('helpdesk_ticket_id', 'helpdesk_ticket_id.sale_order')
    def _compute_ticket_sale_order(self):
        for picking in self:
            ticket = picking.helpdesk_ticket_id
            so = ticket.sale_order if ticket else False
            picking.ticket_sale_order_id = so
            picking.quotation_type = dict(
                so._fields['quotation_type'].selection
            ).get(so.quotation_type, '') if so and hasattr(so, 'quotation_type') else ''
