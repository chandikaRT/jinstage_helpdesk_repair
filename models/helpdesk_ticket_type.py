from odoo import fields, models


class HelpdeskTicketType(models.Model):
    _inherit = 'helpdesk.ticket.type'

    is_rug = fields.Boolean(
        string='RUG', default=False,
        help='True for BOTH "Under Warranty - RUG" and "Under Warranty - External not RUG" types.'
    )
    is_rug_confirmed = fields.Boolean(
        string='RUG Confirmed', default=False,
        help='True ONLY for "Under Warranty - RUG". Gates the full internal approval workflow. '
             '"External not RUG" has is_rug=True but is_rug_confirmed=False — no approval required.'
    )
    is_with_serial_no = fields.Boolean(
        string='With Serial No', default=False,
        help='Enable to require serial number on tickets of this type.'
    )
    is_without_serial_no = fields.Boolean(
        string='Without Serial No', default=False,
        help='Enable for non-serialised repairs. Serial fields hidden on ticket form.'
    )
    rug_account_id = fields.Many2one(
        'account.account', string='RUG Invoice Account',
        help='Account to use for the final invoice on RUG repairs.'
    )
