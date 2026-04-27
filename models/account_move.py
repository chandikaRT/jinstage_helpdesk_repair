from odoo import _, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    rug_account_id = fields.Many2one(
        'account.account', string='RUG Account',
        help='GL account used for RUG (warranty) repair cost postings.'
    )
    is_rug_invoice = fields.Boolean(string='RUG Invoice', default=False)

    def action_update_rug_account(self):
        """Re-route journal entry lines to the RUG GL account."""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('RUG account can only be updated on draft invoices.'))
        if not self.rug_account_id:
            raise UserError(_('Please set a RUG Account before updating journal entries.'))
        product_lines = self.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
        )
        for line in product_lines:
            line.account_id = self.rug_account_id
        self.is_rug_invoice = True
