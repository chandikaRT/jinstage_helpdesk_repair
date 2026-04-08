from odoo import fields, models


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
