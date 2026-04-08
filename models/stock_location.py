from odoo import fields, models


class StockLocation(models.Model):
    _inherit = 'stock.location'

    users_stock_location = fields.Many2many(
        'res.users',
        relation='stock_location_users_rel',
        column1='location_id',
        column2='user_id',
        string='Permitted Users',
        help='Users allowed to process repairs at this location. Empty = all users permitted.'
    )
